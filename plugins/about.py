# A plugin that gives information about the bot.

import settings


class about():
    def about(self, main_ref, msg_info):
        # Ignore private messages
        if msg_info["channel"] == settings.NICK:
            return None
        # Ignore if message does not contain module name
        if not msg_info["message"].startswith("!about"):
            return None

        response = "Running MASTERlinker (https://github.com/Sulter/MASTERlinker). Current systems: core"
        for plugin in main_ref.loaded_plugins:
            plugin_name = plugin.__class__.__name__
            response += ", " + plugin_name
        main_ref.send_msg(msg_info["channel"], response)
