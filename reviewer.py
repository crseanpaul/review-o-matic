import requests
  MAX_CONTEXT = 5

  # Whitelisted patchwork hosts
  PATCHWORK_WHITELIST = [
    'lore.kernel.org',
    'patchwork.freedesktop.org',
    'patchwork.kernel.org',
    'patchwork.linuxtv.org',
    'patchwork.ozlabs.org'
  ]

  def __strip_kruft(self, diff, context):
              LineType.RENAME, LineType.EMPTY]
    ctx_counter = 0
        ctx_counter = 0
        continue

      if l_type == LineType.CONTEXT:
        if ctx_counter < context:
          ret.append(l)
        ctx_counter += 1
        continue

      ctx_counter = 0

      if l_type in ignore:
      else:
        sys.stderr.write('ERROR: line_type not handled {}: {}\n'.format(l_type,
                                                                        l))

    cmd = self.git_cmd + ['log', '--format=oneline', '--abbrev-commit', '-i',
                          '--grep', 'Fixes:.*{}'.format(sha[:8]),
  def get_am_from_from_patch(self, patch):
    regex = re.compile('\(am from (http.*)\)', flags=re.I)
    m = regex.findall(patch)
    if not m or not len(m):
      return None
    return m

  def get_commit_from_patchwork(self, url):
    regex = re.compile('https://([a-z\.]*)/([a-z/]*)/([0-9]*)/')
    m = regex.match(url)
    if not m or not (m.group(1) in self.PATCHWORK_WHITELIST):
      sys.stderr.write('ERROR: URL "%s"\n' % url)
      return None
    return requests.get(url + 'raw/').text

    cmd = self.git_cmd + ['show', '--minimal', '-U{}'.format(self.MAX_CONTEXT),
                          r'--format=%B', sha]
  def compare_diffs(self, a, b, context=0):
    if context > self.MAX_CONTEXT:
      raise ValueError('Invalid context given')

    a = self.__strip_kruft(a, context)
    b = self.__strip_kruft(b, context)