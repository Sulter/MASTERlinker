# A plugin that gives information about the bot.
import includes.helpers as helpers
import subprocess


class about(helpers.Plugin):
  def handle_pm(self, msg_data):
    # Ignore private messages
    pass

  def handle_message(self, msg_data):
    # Ignore if message does not contain module name
    if not msg_data['message'].startswith('!about'):
      return None

    data = {
      'bot_name': 'MASTERlinker <segwit2space>',
      'url': 'https://github.com/Birdulon/MASTERlinker',
      'commit': self.get_commit_info(),
      'plugins': ', '.join(sorted(self.parent.loaded_plugins.keys())),
    }
    response = "Running {bot_name} - version {commit} ({url}). Loaded plugins: {plugins}.".format(**data)
    self.parent.send_msg(msg_data["channel"], response)

  def get_commit_info(self):
    process = subprocess.Popen(['git', 'log', '-1', '--format=%h (%ci)'], shell=False, stdout=subprocess.PIPE)
    return process.communicate()[0].strip().decode('utf-8')
