#!/usr/bin/env python3

from reviewer import Reviewer
from gerrit import Gerrit, GerritRevision, GerritMessage

import argparse
import datetime
import enum
import json
import random
import re
import requests
import sys
import time
import urllib

class ReviewType(enum.Enum):
  SUCCESS = 'success'
  BACKPORT = 'backport'
  ALTERED_UPSTREAM = 'altered_upstream'
  MISSING_FIELDS = 'missing_fields'
  MISSING_HASH = 'missing_hash'
  INCORRECT_PREFIX = 'incorrect_prefix'
  FIXES_REF = 'fixes_ref'

  def __str__(self):
    return self.value
  def __repr__(self):
    return str(self)

class Troll(object):
  STRING_HEADER='''
-- Automated message --
'''
  STRING_SUCCESS='''
This change does not differ from its upstream source. It is certified {}
by review-o-matic!
'''
  STRING_INCORRECT_PREFIX='''
This change has a BACKPORT prefix, however it does not differ from its upstream
source. The BACKPORT prefix should be primarily used for patches which were
altered during the cherry-pick (due to conflicts or downstream inconsistencies).

Consider changing your subject prefix to UPSTREAM (or FROMGIT as appropriate) to
better reflect the contents of this patch.
'''
  STRING_MISSING_FIELDS='''
Your commit message is missing the following required field(s):
    {}
'''
  STRING_MISSING_FIELDS_SUCCESS='''
Don't worry, there is good news! Your patch does not differ from its upstream
source. Once the missing fields are present, it will be certified {} (or some
other similarly official-sounding certification) by review-o-matic!
'''
  STRING_MISSING_FIELDS_DIFF='''
In addition to the missing fields, this patch differs from its upstream source.
This may be expected, this message is posted to make reviewing backports easier.
'''
  STRING_MISSING_HASH_HEADER='''
Your commit message is missing the upstream commit hash. It should be in the
form:
'''
  STRING_MISSING_HASH_FMT_FROMGIT='''
    (cherry picked from commit <commit SHA>
     <remote git url> <remote git tree>)
'''
  STRING_MISSING_HASH_FMT_UPSTREAM='''
    (cherry picked from commit <commit SHA>)
'''
  STRING_MISSING_HASH_FOOTER='''
Hint: Use the '-x' argument of git cherry-pick to add this automagically
'''
  STRING_UNSUCCESSFUL_HEADER='''
This patch differs from the source commit.

'''
  STRING_UPSTREAM_DIFF='''
Since this is an UPSTREAM labeled patch, it shouldn't. Either this reviewing
script is incorrect (totally possible, pls send patches!), or something changed
when this was backported. If the backport required changes, please consider
using the BACKPORT label with a description of you downstream changes in your
commit message.
'''
  STRING_BACKPORT_DIFF='''
This is expected, and this message is posted to make reviewing backports easier.
'''
  STRING_FROMGIT_DIFF='''
This may be expected, this message is posted to make reviewing backports easier.
'''
  STRING_UNSUCCESSFUL_FOOTER='''
Below is a diff of the upstream patch referenced in this commit message, vs this
patch.

'''
  STRING_FOUND_FIXES_REF='''
!! NOTE: This patch has been referenced in the Fixes: tag of another commit. If
!!       you haven't already, consider backporting the following patch:
!!  {}
'''
  STRING_FOOTER='''
---
To learn more about backporting kernel patches to Chromium OS, check out:
  https://chromium.googlesource.com/chromiumos/docs/+/master/kernel_faq.md#UPSTREAM_BACKPORT_FROMLIST_and-you

If you're curious about how this message was generated, head over to:
  https://github.com/atseanpaul/review-o-matic

This link is not useful:
  https://thats.poorly.run/
'''

  SWAG = ['Frrrresh', 'Crisper Than Cabbage', 'Awesome', 'Ahhhmazing',
          'Cool As A Cucumber', 'Most Excellent', 'Eximious', 'Prestantious',
          'Supernacular', 'Bodacious', 'Blue Chip', 'Blue Ribbon', 'Cracking',
          'Dandy', 'Dynamite', 'Fab', 'Fabulous', 'Fantabulous',
          'Scrumtrulescent', 'First Class', 'First Rate', 'First String',
          'Five Star', 'Gangbusters', 'Grand', 'Groovy', 'HYPE', 'Jim-Dandy',
          'Snazzy', 'Marvelous', 'Nifty', 'Par Excellence', 'Peachy Keen',
          'PHAT', 'Prime', 'Prizewinning', 'Quality', 'Radical', 'Righteous',
          'Sensational', 'Slick', 'Splendid', 'Lovely', 'Stellar', 'Sterling',
          'Superb', 'Superior', 'Superlative', 'Supernal', 'Swell', 'Terrific',
          'Tip-Top', 'Top Notch', 'Top Shelf', 'Unsurpassed', 'Wonderful']

  def __init__(self, url, args):
    self.url = url
    self.args = args
    self.gerrit = Gerrit(url)
    self.tag = 'autogenerated:review-o-matic'
    self.blacklist = []
    self.stats = { str(ReviewType.SUCCESS): 0, str(ReviewType.BACKPORT): 0,
                   str(ReviewType.ALTERED_UPSTREAM): 0,
                   str(ReviewType.MISSING_FIELDS): 0,
                   str(ReviewType.MISSING_HASH): 0,
                   str(ReviewType.INCORRECT_PREFIX): 0,
                   str(ReviewType.FIXES_REF): 0 }

  def inc_stat(self, review_type):
    self.stats[str(review_type)] += 1

  def do_review(self, review_type, change, fixes_ref, msg, notify, vote):
    final_msg = self.STRING_HEADER
    if fixes_ref:
      print('Adding fixes ref for change {}'.format(change.url()))
      self.inc_stat(ReviewType.FIXES_REF)
      final_msg += self.STRING_FOUND_FIXES_REF.format(fixes_ref)
    final_msg += msg
    final_msg += self.STRING_FOOTER

    self.inc_stat(review_type)
    if not self.args.dry_run:
      self.gerrit.review(change, self.tag, final_msg, notify,
                         vote_code_review=vote)
    else:
      print('Review for change: {}'.format(change.url()))
      print('  Type:{}, Vote:{}, Notify:{}'.format(review_type, vote, notify))
      print(final_msg)
      print('------')

  def handle_successful_review(self, change, prefix, fixes_ref):
    if prefix == 'BACKPORT':
      print('Adding incorrect prefix review for change {}'.format(change.url()))
      msg = self.STRING_INCORRECT_PREFIX
      self.do_review(ReviewType.INCORRECT_PREFIX, change, fixes_ref, msg, True,
                     0)
    else:
      print('Adding successful review for change {}'.format(change.url()))
      msg = self.STRING_SUCCESS.format(random.choice(self.SWAG))
      self.do_review(ReviewType.SUCCESS, change, fixes_ref, msg, True, 1)


  def handle_missing_fields_review(self, change, fields, result, fixes_ref):
    print('Adding missing fields review for change {}'.format(change.url()))
    missing = []
    if not fields['bug']:
      missing.append('BUG=')
    if not fields['test']:
      missing.append('TEST=')
    if not fields['sob']:
      cur_rev = change.current_revision
      missing.append('Signed-off-by: {} <{}>'.format(cur_rev.uploader_name,
                                                     cur_rev.uploader_email))

    msg = self.STRING_MISSING_FIELDS.format(', '.join(missing))
    if len(result) == 0:
      msg += self.STRING_MISSING_FIELDS_SUCCESS.format(random.choice(self.SWAG))
    else:
      msg += self.STRING_MISSING_FIELDS_DIFF
      msg += self.STRING_UNSUCCESSFUL_FOOTER
      for l in result:
        msg += '{}\n'.format(l)

    self.do_review(ReviewType.MISSING_FIELDS, change, fixes_ref, msg, True, -1)

  def handle_missing_hash_review(self, change,  prefix):
    print('Adding missing hash review for change {}'.format(change.url()))
    msg = self.STRING_MISSING_HASH_HEADER
    if prefix == 'FROMGIT':
      msg += self.STRING_MISSING_HASH_FMT_FROMGIT
    else:
      msg += self.STRING_MISSING_HASH_FMT_UPSTREAM
    msg += self.STRING_MISSING_HASH_FOOTER
    self.do_review(ReviewType.MISSING_HASH, change, None, msg, True, -1)

  def handle_unsuccessful_review(self, change, prefix, result, fixes_ref):
    vote = 0
    notify = False
    review_type = ReviewType.BACKPORT

    msg = self.STRING_UNSUCCESSFUL_HEADER
    if prefix == 'UPSTREAM':
      review_type = ReviewType.ALTERED_UPSTREAM
      vote = -1
      notify = True
      msg += self.STRING_UPSTREAM_DIFF
    elif prefix == 'BACKPORT':
      msg += self.STRING_BACKPORT_DIFF
    elif prefix == 'FROMGIT':
      msg += self.STRING_FROMGIT_DIFF

    msg += self.STRING_UNSUCCESSFUL_FOOTER

    for l in result:
      msg += '{}\n'.format(l)

    print('Adding unsuccessful review (vote={}) for change {}'.format(vote,
          change.url()))

    self.do_review(review_type, change, fixes_ref, msg, notify, vote)


  def get_changes(self, prefix):
    message = '{}:'.format(prefix)
    after = datetime.date.today() - datetime.timedelta(days=5)
    changes = self.gerrit.query_changes(status='open', message=message,
                    after=after, project='chromiumos/third_party/kernel')
    return changes

  def print_error(self, error):
    if self.args.verbose:
      sys.stderr.write('\n')
    sys.stderr.write(error)

  def process_changes(self, prefix, changes):
    rev = Reviewer(git_dir=self.args.git_dir, verbose=self.args.verbose,
                   chatty=self.args.chatty)
    num_changes = len(changes)
    cur_change = 1
    line_feed = False
    ret = False
    for c in changes:
      cur_rev = c.current_revision

      if self.args.chatty:
        print('Processing change {}'.format(c.url()))
      elif self.args.verbose:
        sys.stdout.write('{}Processing change {}/{}'.format(
                            '\r' if line_feed else '',
                            cur_change, num_changes))
        cur_change += 1

      line_feed = True

      if c in self.blacklist:
        continue

      if not c.subject.startswith(prefix) or 'FROMLIST' in c.subject:
        continue

      skip = False
      for m in c.messages:
        if m.tag == self.tag and m.revision_num == cur_rev.number:
          skip = True
      if skip and not self.args.force_cl:
        continue

      ret = True
      line_feed = False
      if self.args.verbose:
        print('')

      gerrit_patch = rev.get_commit_from_remote('cros', cur_rev.ref)

      upstream_shas = rev.get_cherry_pick_shas_from_patch(gerrit_patch)
      if not upstream_shas:
        self.handle_missing_hash_review(c, prefix)
        continue

      upstream_patch = None
      upstream_sha = None
      for s in reversed(upstream_shas):
        try:
          upstream_patch = rev.get_commit_from_sha(s)
          upstream_sha = s
          break
        except:
          continue
      if not upstream_patch:
        self.print_error('ERROR: SHA missing from git for {} ({})\n'.format(
                                    c, upstream_shas))
        self.blacklist.append(c)
        continue

      fixes_ref = rev.find_fixes_reference(upstream_sha)

      result = rev.compare_diffs(upstream_patch, gerrit_patch)

      fields={'sob':False, 'bug':False, 'test':False}
      sob_re = re.compile('Signed-off-by:\s+{}'.format(cur_rev.uploader_name))
      for l in cur_rev.commit_message.splitlines():
        if l.startswith('BUG='):
          fields['bug'] = True
          continue
        if l.startswith('TEST='):
          fields['test'] = True
          continue
        if sob_re.match(l):
          fields['sob'] = True
          continue
      if not fields['bug'] or not fields['test'] or not fields['sob']:
        self.handle_missing_fields_review(c, fields, result, fixes_ref)
        continue

      if len(result) == 0:
        self.handle_successful_review(c, prefix, fixes_ref)
        continue

      self.handle_unsuccessful_review(c, prefix, result, fixes_ref)

    if self.args.verbose:
      print('')

    return ret

  def update_stats(self):
    if not self.args.dry_run and self.args.stats_file:
      with open(self.args.stats_file, 'wt') as f:
        json.dump(self.stats, f)
    print('--')
    summary = '  Summary: '
    for k,v in self.stats.items():
      summary += '{}={} '.format(k,v)
    print(summary)
    print('')

  def run(self):
    if self.args.force_cl:
      c = self.gerrit.get_change(self.args.force_cl)
      prefix = c.subject.split(':')[0]
      print('Force reviewing change  {}'.format(c))
      self.process_changes(prefix, [c])
      return

    if self.args.stats_file:
      try:
        with open(self.args.stats_file, 'rt') as f:
          self.stats = json.load(f)
      except FileNotFoundError:
        self.update_stats()

    while True:
      try:
        prefixes = ['UPSTREAM', 'BACKPORT', 'FROMGIT']
        did_review = False
        for p in prefixes:
          changes = self.get_changes(p)
          if self.args.verbose:
            print('{} changes for prefix {}'.format(len(changes), p))
          did_review |= self.process_changes(p, changes)
        if did_review:
          self.update_stats()
        if not self.args.daemon:
          break
        if self.args.verbose:
          print('Finished! Going to sleep until next run')

      except requests.exceptions.HTTPError as e:
        self.print_error('HTTPError ({})\n'.format(e.response.status_code))
        time.sleep(60)

      time.sleep(120)


def main():
  parser = argparse.ArgumentParser(description='Troll gerrit reviews')
  parser.add_argument('--git-dir', default=None, help='Path to git directory')
  parser.add_argument('--verbose', help='print commits', action='store_true')
  parser.add_argument('--chatty', help='print diffs', action='store_true')
  parser.add_argument('--daemon', action='store_true',
    help='Run in daemon mode, for continuous trolling')
  parser.add_argument('--dry-run', action='store_true', default=False,
                      help='skip the review step')
  parser.add_argument('--force-cl', default=None, help='Force review a CL')
  parser.add_argument('--stats-file', default=None, help='Path to stats file')
  args = parser.parse_args()

  troll = Troll('https://chromium-review.googlesource.com', args)
  troll.run()

if __name__ == '__main__':
  sys.exit(main())
