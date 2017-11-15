# A plugin that gives information about the bot.


class about():
  def about(self, main_ref, msg_info):
    # Ignore private messages
    if msg_info["channel"] == main_ref.config['connection']['nick']:
      return None
    # Ignore if message does not contain module name
    if not msg_info["message"].startswith("!about"):
      return None

    response = "Running MASTERlinker segwit2space (https://github.com/Birdulon/MASTERlinker). Loaded plugins: "
    response += ', '.join(sorted(main_ref.loaded_plugins.keys()))
    main_ref.send_msg(msg_info["channel"], response)
