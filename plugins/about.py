# A plugin that gives information about the bot.
import subprocess


class about():
  def about(self, main_ref, msg_info):
    # Ignore private messages
    if msg_info['channel'] == main_ref.config['connection']['nick']:
      return None
    # Ignore if message does not contain module name
    if not msg_info['message'].startswith('!about'):
      return None

    data = {
      'bot_name': 'MASTERlinker <segwit2space>',
      'url': 'https://github.com/Birdulon/MASTERlinker',
      'commit': self.get_commit_info(),
      'plugins': ', '.join(sorted(main_ref.loaded_plugins.keys())),
    }
    response = "Running {bot_name} - version {commit} ({url}). Loaded plugins: {plugins}.".format(**data)
    main_ref.send_msg(msg_info["channel"], response)

  def get_commit_info(self):
    process = subprocess.Popen(['git', 'log', '-1', '--format=%h (%ci)'], shell=False, stdout=subprocess.PIPE)
    return process.communicate()[0].strip().decode('utf-8')
