# A plugin that gives information about the bot.
import settings

class about():
    # Main function.
    def about(self, main_ref, msg_info):
        # We'll guard against PMs.
        if msg_info["channel"] == settings.NICK:
            return None
        #We'll also ignore any calls not starting with !about.
        if not msg_info["message"].startswith("!about"):
            return None
        #Generate a response and output it.
        response = "Running MASTERlinker (https://github.com/Sulter/MASTERlinker). Current systems: core"
        for plugin in main_ref.loaded_plugins:
            plugin_name = plugin.__class__.__name__
            response += ", " + plugin_name;
        main_ref.send_msg(msg_info["channel"], response)

