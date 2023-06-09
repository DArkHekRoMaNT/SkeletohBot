import logging
import traceback

import db
from models import ChatMessage, ChatBot, PointsType

_log = logging.getLogger(__name__)

command_prefix = '!'
commands = []
active_modules = ['base']


def enable_module(name: str):
    active_modules.append(name)


def disable_module(name: str):
    if name in active_modules:
        active_modules.remove(name)


def command(name: str, *, aliases=None, owner_only=False, roles_required=None,
            elixir: int = 0, mana: int = 0, module: str = 'base'):
    if aliases is None:
        aliases = []

    def decorator(func):
        def can_execute(msg: ChatMessage) -> bool:
            if module not in active_modules:
                return False

            if owner_only:
                return msg.roles.__contains__('streamer') or msg.roles.__contains__('broadcaster')

            if roles_required:
                for role in roles_required:
                    if msg.roles.__contains__(role):
                        return True
                return False

            return True

        def wrapper(msg: ChatMessage, bot: ChatBot):
            user = msg.sender
            username = user.name

            def has_pay() -> bool:
                if user.mana >= mana >= 0 or user.elixir >= elixir >= 0:
                    return True

                if mana > 0 and elixir > 0:
                    bot.send_message(f"@{username} не хватает ({elixir} ep или {mana} mp)")
                elif elixir > 0:
                    bot.send_message(f"@{username} не хватает ({elixir} ep)")
                elif mana > 0:
                    bot.send_message(f"@{username} не хватает ({mana} mp)")

                _log.debug(f'Can\'t pay for trigger command "{name}": {msg.text} by {username}')
                return False

            prefix = msg.text.split(maxsplit=1)[0].lower()
            if any([cmd for cmd in [*aliases, name] if prefix == command_prefix + cmd]):
                if can_execute(msg) and has_pay():
                    _log.debug(f'Trigger command "{name}": {msg.text} by {username}')
                    try:
                        func(msg, bot)

                        if user.mana >= mana > 0:
                            db.add_points(user, -mana, PointsType.Mana)
                        elif user.elixir >= elixir > 0:
                            db.add_points(user, -elixir, PointsType.Elixir)

                    except Exception as e:
                        _log.error(f'Error during execute {name} by {username}: {e}')
                        _log.debug(traceback.format_exc())
                else:
                    _log.debug(f'Reject command "{name}": {msg.text} by {username} (no privileges)')

        if not hasattr(wrapper, 'registered') or wrapper.registered is False:
            wrapper.registered = True
            wrapper.can_execute = can_execute
            wrapper.help_text = command_prefix + name
            wrapper.name = name
            wrapper.module = module
            commands.append(wrapper)
        return wrapper

    return decorator


@command('help', aliases=['помощь'])
def help_command(msg: ChatMessage, bot: ChatBot):
    help_text = {}
    for cmd in commands:
        if cmd.can_execute(msg):
            try:
                help_text[cmd.module].append(cmd.help_text)
            except KeyError:
                help_text[cmd.module] = list()
                help_text[cmd.module].append(cmd.help_text)

    if len(help_text) == 0:
        bot.send_message('No available commands')
    else:
        for value in help_text.values():
            text = '\u200c' + ' '.join(value)  # add zero-width space first for prevent loop
            bot.send_message(text)


@command('module_on', owner_only=True)
def enable_module_command(msg: ChatMessage, bot: ChatBot):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return

    module = args[1]
    enable_module(module)
    bot.send_message(f'Module {module} on')


@command('module_off', owner_only=True)
def disable_module_command(msg: ChatMessage, bot: ChatBot):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return

    module = args[1]
    disable_module(module)
    bot.send_message(f'Module {module} off')


def trigger_commands(msg: ChatMessage, bot: ChatBot):
    for cmd in commands:
        try:
            cmd(msg, bot)
        except Exception as e:
            _log.warning(f'Trigger command {cmd.name} by {msg.sender.name} is failed: {e}')
            _log.debug(traceback.format_exc())
