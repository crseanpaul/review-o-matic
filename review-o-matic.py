  SIMILARITY = 'similarity index ([0-9]+)%'
  RENAME = 'rename (from|to) (.*)'
  ignore = [Type.CHUNK, Type.GITDIFF, Type.INDEX, Type.DELETED, Type.ADDED,
            Type.SIMILARITY, Type.RENAME]
      sys.stderr.write('ERROR: Could not classify line "%s"\n' % l)
    return 1
  cmd = ['git', 'log', '--oneline', '{c}^..{c}'.format(c=commit)]
  oneline = subprocess.check_output(cmd).decode('UTF-8').rstrip()
    print('Reviewing %s (rmt=%s)' % (oneline, upstrm[:11]))
  for l in reversed(proc.decode('UTF-8').split('\n')):
    this_ret = 0
      this_ret = review_change(m.group(1), args.verbose, args.chatty)
    if this_ret and (args.verbose or args.chatty):
      print('')
    ret += this_ret
