# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>

import os

from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository)

from tests.component.deb import DEB_TEST_DATA_DIR
from tests.component.deb.fixtures import RepoFixtures

from nose.tools import ok_, eq_

from gbp.scripts.pq import main as pq
from gbp.scripts.import_dsc import main as import_dsc

from subprocess import check_output as run


class TestPq(ComponentTestBase):
    """Test gbp pq"""

    def _test_pq(self, repo, action, opts=[]):
        args = ['arg0', action] + opts
        os.chdir(os.path.abspath(repo.path))
        ret = pq(args)
        ok_(ret == 0, "Running gbp pq %s failed" % action)

    @RepoFixtures.quilt30()
    def test_rebase_import(self, repo):
        """Test that rebase imports patches first"""
        eq_(repo.branch, 'master')
        eq_(repo.has_branch('patch-queue/master'), False)
        self._test_pq(repo, 'rebase')
        eq_(repo.has_branch('patch-queue/master'), True)

    @RepoFixtures.quilt30()
    def test_switch_import(self, repo):
        """Test that switch imports patches first"""
        eq_(repo.branch, 'master')
        eq_(repo.has_branch('patch-queue/master'), False)
        self._test_pq(repo, 'switch')
        eq_(repo.has_branch('patch-queue/master'), True)

    @RepoFixtures.quilt30()
    def test_empty_cycle(self, repo):
        eq_(repo.has_branch('patch-queue/master'), False)
        eq_(repo.branch, 'master')
        self._test_pq(repo, 'import')
        eq_(repo.has_branch('patch-queue/master'), True)
        eq_(repo.branch, 'patch-queue/master')
        self._test_pq(repo, 'rebase')
        eq_(repo.branch, 'patch-queue/master')
        self._test_pq(repo, 'export')
        eq_(repo.has_branch('patch-queue/master'), True)
        eq_(repo.branch, 'master')
        self._test_pq(repo, 'drop')
        eq_(repo.has_branch('patch-queue/master'), False)

    @RepoFixtures.quilt30()
    def test_rename(self, repo):
        patch = os.path.join(repo.path, 'debian/patches/0001-Rename.patch')

        repo.set_config('diff.renames', 'true')
        self._test_pq(repo, 'import')
        repo.rename_file('configure.ac', 'renamed')
        repo.commit_all("Rename")
        self._test_pq(repo, 'export')
        self.assertTrue(
            os.path.exists(patch))
        # Check the file was removed and added, not renamed
        with open(patch) as f:
            self.assertTrue('rename from' not in f.read())
            self.assertTrue('rename to' not in f.read())

    @staticmethod
    def _dsc_name(pkg, version, dir):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.dsc' % (pkg, version))

    @staticmethod
    def _get_head_author_subject():
        output = run('git format-patch -1 --stdout --subject-prefix=', shell=True)
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                # end of headers
                break
            if line.startswith('From:'):
                author = line.replace('From:', '').strip()
            elif line.startswith('Subject:'):
                subject = line.replace('Subject:', ''). strip()
        return author, subject

    def test_import(self):
        '''Test importing some patches'''

        pkg = 'hello-debhelper'
        dsc = self._dsc_name(pkg, '2.6-2', 'dsc-3.0')
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository(pkg)
        os.chdir(pkg)
        ret = pq(['arg0', 'import'])
        ok_(ret == 0, 'Importing patches failed')

        author, subject = self._get_head_author_subject()
        assert (author == 'Santiago Vila <sanvila@debian.org>' and
                subject == 'Modified doc/Makefile.in to avoid '
                           '/usr/share/info/dir.gz')

        pq(['arg0', 'switch'])

        with open('debian/patches/series', 'a') as series_file:
            series_file.write('foo.patch\n')

        with open('debian/patches/foo.patch', 'w') as patch:
            patch.write('''\
Author: Mr. T. St <t@example.com>
Description: Short DEP3 description
 Long DEP3 description
 .
 Continued
--- /dev/null
+++ b/foo
@@ -0,0 +1 @@
+foo
''')
        repo.add_files('debian/patches/foo.patch')
        repo.commit_files(msg='Add patch: foo.patch',
                          files=['debian/patches/series',
                                 'debian/patches/foo.patch'])
        ret = pq(['arg0', 'import', '--force'])
        ok_(ret == 0, 'Importing foo.patch failed')

        author, subject = self._get_head_author_subject()
        assert (author == '"Mr. T. St" <t@example.com>' and
                subject == 'Short DEP3 description')
