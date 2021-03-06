import re

from trollreview import ReviewResult
from trollreview import ReviewType
from trollreviewergit import GitChangeReviewer
from trollstrings import ReviewStrings

class FromgitReviewStrings(ReviewStrings):
  HASH_EXAMPLE='''
    (cherry picked from commit <commit SHA>
     <remote git url> <remote git branch>)
'''
  INVALID_HASH_FOOTER='''
Please double check your commit hash is valid in the upstream tree, and please
fully specify the remote tree and branch for FROMGIT changes (see below):
'''
  CLEAN_BACKPORT_FOOTER='''
Consider changing your subject prefix to FROMGIT to better reflect the
contents of this patch.
'''
  PATCH_IN_MAINLINE='''
This patch is labeled as FROMGIT, however it seems like it's already been
applied to mainline. Please revise your patch subject to replace FROMGIT with
UPSTREAM.
'''
  PATCH_IN_FORBIDDEN_TREE='''
The remote listed on this patch is in a forbidden tree. Integration and rebasing
trees are unacceptable sources of patches since their commit sha can change.

Please source either a non-rebasing maintainer tree or a mailing list post. See
the link below on backporting for more information.
'''

class FromgitChangeReviewer(GitChangeReviewer):
  def __init__(self, project, reviewer, change, msg_limit, dry_run,
               days_since_last_review):
    super().__init__(project, reviewer, change, msg_limit, dry_run)
    self.strings = FromgitReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)
    self.days_since_last_review = days_since_last_review

  @staticmethod
  def can_review_change(project, change, days_since_last_review):
    # Don't re-review for 14 days
    if days_since_last_review != None and days_since_last_review < 14:
      return False

    return 'FROMGIT' in project.prefixes and 'FROMGIT' in change.subject

  def add_patch_in_mainline_review(self):
    self.review_result.add_review(ReviewType.IN_MAINLINE,
                                  self.strings.PATCH_IN_MAINLINE, vote=-1,
                                  notify=True)

  def is_remote_in_blocked_repos(self):
    if not self.upstream_ref:
      return False

    for b in self.project.blocked_repos:
      if re.match(b, self.upstream_ref.remote, re.I):
        return True
    return False

  def add_patch_in_forbidden_tree(self):
    self.review_result.add_review(ReviewType.FORBIDDEN_TREE,
                                  self.strings.PATCH_IN_FORBIDDEN_TREE, vote=-1,
                                  notify=True)

  def get_upstream_patch(self):
    super().get_upstream_patch()

    if self.is_sha_in_mainline():
      self.add_patch_in_mainline_review()
    elif self.is_remote_in_blocked_repos():
      self.add_patch_in_forbidden_tree()

  def review_patch(self):
    result = super().review_patch()

    # Only re-review patches if we're adding an IN_MAINLINE review
    if (self.days_since_last_review != None and
        ReviewType.IN_MAINLINE not in result.issues):
      return None

    return result
