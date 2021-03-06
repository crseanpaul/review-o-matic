#!/usr/bin/python3

import argparse
import json
import logging
import subprocess
import sys
import time

from gerrit import Gerrit

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

class Submitter(object):
  def __init__(self, last_cid, review, verify, ready, abandon, force_review,
               dry_run):
    self.abandon = abandon
    self.vote_review = 2 if review else None
    self.vote_verify = 1 if verify else None
    self.vote_cq_ready = ready
    self.force_review = force_review

    self.dry_run = dry_run

    self.tag = 'autogenerated:submit-o-matic'

    self.max_in_flight = 100 # 50 for the cq, 50 for the pre-cq
    self.in_flight = []

    self.changes = []
    self.gerrit = Gerrit('https://chromium-review.googlesource.com',
                         use_internal=False)
    last_change = self.gerrit.get_change(last_cid)
    ancestor_changes = self.gerrit.get_ancestor_changes(last_change)
    for c in reversed(ancestor_changes):
        if c.status == 'NEW':
          self.changes.append(c)
    self.changes.append(last_change)

  def change_needs_action(self, change):
    return change.is_merged() or \
           (self.vote_review and not change.is_reviewed()) or \
           (self.vote_verify and not change.is_verified()) or \
           (self.vote_cq_ready and not change.is_cq_ready())

  def num_changes(self):
    return len(self.changes)

  def num_in_flight(self):
    return len(self.in_flight)

  def review_changes(self):
    if not self.vote_review and not self.vote_verify and not self.abandon:
      return

    for i,c in enumerate(self.changes):
      sys.stdout.write('\rRunning reviewer (%d/%d)' % (i, self.num_changes()))
      c = self.gerrit.get_change(c.number)

      if self.abandon:
        if not self.dry_run:
          self.gerrit.abandon(c)
        else:
          print('DRYRUN abandon {}'.format(c))
        continue

      if (c.is_merged() or not self.change_needs_action(c)) and not self.force_review:
        continue

      if not self.dry_run:
        self.gerrit.review(c, self.tag, '', False, self.vote_review,
                          self.vote_verify, None)
      else:
        print('DRYRUN review (r={}, v={}) {}'.format(self.vote_review,
                                                     self.vote_verify,
                                                     c))

  def submit_changes(self):
    if self.abandon:
      return

    self.in_flight = []
    merged = 0
    for i,c in enumerate(self.changes):
      if self.num_in_flight() >= self.max_in_flight:
        break

      sys.stdout.write('\rRunning submitter (%d/%d)' % (i, self.num_changes()))
      c = self.gerrit.get_change(c.id)
      if c.is_merged():
        merged += 1
        continue

      if self.change_needs_action(c):
        if not self.dry_run:
          self.gerrit.review(c, self.tag, '', False, self.vote_review,
                            self.vote_verify, self.vote_cq_ready)
        else:
          print('DRYRUN review (r={}, v={} cq={}) {}'.format(self.vote_review,
                                                      self.vote_verify,
                                                      self.vote_cq_ready,
                                                      c))

      self.in_flight.append(c)

    sys.stdout.write('\r%d Changes:                                       \n' %
                     self.num_changes())
    sys.stdout.write('-- %d merged\n' %  merged)
    sys.stdout.write('-- %d in flight\n' %  self.num_in_flight())

  def detect_change(self):
    if self.num_in_flight() == 0: # everything is merged, so no detection needed
      return True

    c = self.in_flight[0]
    sys.stdout.write('\rDetecting: %s' % c.url())
    c = self.gerrit.get_change(c.id)
    if self.change_needs_action(c):
      return True

    return False


def main():
  parser = argparse.ArgumentParser(description='Auto review/submit gerrit cls')
  parser.add_argument('--last-cid', default=None, required=True,
    help='Gerrit change-id of last patch in set')
  parser.add_argument('--daemon', action='store_true',
    help='Run in daemon mode, continuously update changes until merged')
  parser.add_argument('--review', action='store_true',
    help='Mark changes as reviewed')
  parser.add_argument('--verify', action='store_true',
    help='Mark changes as verified')
  parser.add_argument('--ready', action='store_true',
    help='Mark changes as ready')
  parser.add_argument('--force-review', action='store_true',
    help='Force reviewer to act on all patches in the series')
  parser.add_argument('--tryjob', action='store_true',
    help='Mark changes as ready +1 (tryjob)')
  parser.add_argument('--abandon', action='store_true', help='Abandon changes')
  parser.add_argument('--dry-run', action='store_true', help='Practice makes perfect')
  parser.add_argument('--max-tries', default=5, help='Max number to try submit in daemon mode', type=int)
  args = parser.parse_args()

  ready = None
  if args.ready:
    ready = 2
  elif args.tryjob:
    ready = 1

  s = Submitter(args.last_cid, args.review, args.verify, ready, args.abandon,
                args.force_review, args.dry_run)
  s.review_changes()
  tries = 0
  while True:
    s.submit_changes()
    if s.num_in_flight() == 0:
      sys.stdout.write('\n\nCongratulations, your changes have landed!\n\n')
      return True

    if not args.daemon:
      break

    if tries >= args.max_tries:
      sys.stdout.write('\n\nMax tries exceeded!\n\n')
      return False
    tries += 1

    while True:
      sys.stdout.write('\rSleeping...                                        ')
      if s.detect_change():
        break
      time.sleep(60)

if __name__ == '__main__':
  sys.exit(main())
