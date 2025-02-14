# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.loader
    ~~~~~~~~~~~~~~~~~~~~~~~

    Test the loaders.

    :copyright: (c) 2017 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import os
import shutil
import sys
import time
import tempfile
import weakref

import pytest

from jinja2 import Environment
from jinja2 import loaders
from jinja2 import PackageLoader
from jinja2._compat import PY2
from jinja2._compat import PYPY
from jinja2.exceptions import TemplateNotFound
from jinja2.loaders import split_template_path


@pytest.mark.loaders
class TestLoaders(object):
    def test_dict_loader(self, dict_loader):
        env = Environment(loader=dict_loader)
        tmpl = env.get_template('justdict.html')
        assert tmpl.render().strip() == 'FOO'
        pytest.raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_package_loader(self, package_loader):
        env = Environment(loader=package_loader)
        tmpl = env.get_template('test.html')
        assert tmpl.render().strip() == 'BAR'
        pytest.raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_filesystem_loader_overlapping_names(self, filesystem_loader):
        res = os.path.dirname(filesystem_loader.searchpath[0])
        t2_dir = os.path.join(res, "templates2")
        # Make "foo" show up before "foo/test.html".
        filesystem_loader.searchpath.insert(0, t2_dir)
        e = Environment(loader=filesystem_loader)
        e.get_template("foo")
        # This would raise NotADirectoryError if "t2/foo" wasn't skipped.
        e.get_template("foo/test.html")
        assert len(filesystem_loader.searchpath) == 2
        fullpath = os.path.join(filesystem_loader.searchpath[1], "foo", "test.html")
        assert os.path.exists(fullpath)
        if filesystem_loader.strict:
            pytest.raises(TemplateNotFound, e.get_template, fullpath)
        else:
            assert e.get_template(fullpath).render().strip() == 'FOO'

    def test_filesystem_loader_nostrict(self, filesystem_loader_nostrict):
        self.test_filesystem_loader_overlapping_names(filesystem_loader_nostrict)

    def test_choice_loader(self, choice_loader):
        env = Environment(loader=choice_loader)
        tmpl = env.get_template('justdict.html')
        assert tmpl.render().strip() == 'FOO'
        tmpl = env.get_template('test.html')
        assert tmpl.render().strip() == 'BAR'
        pytest.raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_function_loader(self, function_loader):
        env = Environment(loader=function_loader)
        tmpl = env.get_template('justfunction.html')
        assert tmpl.render().strip() == 'FOO'
        pytest.raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_prefix_loader(self, prefix_loader):
        env = Environment(loader=prefix_loader)
        tmpl = env.get_template('a/test.html')
        assert tmpl.render().strip() == 'BAR'
        tmpl = env.get_template('b/justdict.html')
        assert tmpl.render().strip() == 'FOO'
        pytest.raises(TemplateNotFound, env.get_template, 'missing')

    def test_caching(self):
        changed = False

        class TestLoader(loaders.BaseLoader):
            def get_source(self, environment, template):
                return u'foo', None, lambda: not changed
        env = Environment(loader=TestLoader(), cache_size=-1)
        tmpl = env.get_template('template')
        assert tmpl is env.get_template('template')
        changed = True
        assert tmpl is not env.get_template('template')
        changed = False

    def test_no_cache(self):
        mapping = {'foo': 'one'}
        env = Environment(loader=loaders.DictLoader(mapping), cache_size=0)
        assert env.get_template('foo') is not env.get_template('foo')

    def test_limited_size_cache(self):
        mapping = {'one': 'foo', 'two': 'bar', 'three': 'baz'}
        loader = loaders.DictLoader(mapping)
        env = Environment(loader=loader, cache_size=2)
        t1 = env.get_template('one')
        t2 = env.get_template('two')
        assert t2 is env.get_template('two')
        assert t1 is env.get_template('one')
        t3 = env.get_template('three')
        loader_ref = weakref.ref(loader)
        assert (loader_ref, 'one') in env.cache
        assert (loader_ref, 'two') not in env.cache
        assert (loader_ref, 'three') in env.cache

    def test_cache_loader_change(self):
        loader1 = loaders.DictLoader({'foo': 'one'})
        loader2 = loaders.DictLoader({'foo': 'two'})
        env = Environment(loader=loader1, cache_size=2)
        assert env.get_template('foo').render() == 'one'
        env.loader = loader2
        assert env.get_template('foo').render() == 'two'

    def test_dict_loader_cache_invalidates(self):
        mapping = {'foo': "one"}
        env = Environment(loader=loaders.DictLoader(mapping))
        assert env.get_template('foo').render() == "one"
        mapping['foo'] = "two"
        assert env.get_template('foo').render() == "two"

    def test_split_template_path(self):
        assert split_template_path('foo/bar') == ['foo', 'bar']
        assert split_template_path('./foo/bar') == ['foo', 'bar']
        pytest.raises(TemplateNotFound, split_template_path, '../foo')


@pytest.mark.loaders
@pytest.mark.filesystemloader
class TestFileSystemLoader(object):
    searchpath = os.path.dirname(os.path.abspath(__file__)) + '/res/templates'

    @staticmethod
    def _test_common(env):
        tmpl = env.get_template('test.html')
        assert tmpl.render().strip() == 'BAR'
        tmpl = env.get_template('foo/test.html')
        assert tmpl.render().strip() == 'FOO'
        pytest.raises(TemplateNotFound, env.get_template, 'missing.html')

    def test_searchpath_as_str(self):
        filesystem_loader = loaders.FileSystemLoader(self.searchpath)

        env = Environment(loader=filesystem_loader)
        self._test_common(env)

    @pytest.mark.skipif(PY2, reason='pathlib is not available in Python 2')
    def test_searchpath_as_pathlib(self):
        import pathlib
        searchpath = pathlib.Path(self.searchpath)

        filesystem_loader = loaders.FileSystemLoader(searchpath)

        env = Environment(loader=filesystem_loader)
        self._test_common(env)

    @pytest.mark.skipif(PY2, reason='pathlib is not available in Python 2')
    def test_searchpath_as_list_including_pathlib(self):
        import pathlib
        searchpath = pathlib.Path(self.searchpath)

        filesystem_loader = loaders.FileSystemLoader(['/tmp/templates', searchpath])

        env = Environment(loader=filesystem_loader)
        self._test_common(env)

    def test_caches_template_based_on_mtime(self):
        filesystem_loader = loaders.FileSystemLoader(self.searchpath)

        env = Environment(loader=filesystem_loader)
        tmpl1 = env.get_template('test.html')
        tmpl2 = env.get_template('test.html')
        assert tmpl1 is tmpl2

        os.utime(
            os.path.join(self.searchpath, "test.html"),
            (time.time(), time.time())
        )
        tmpl3 = env.get_template('test.html')
        assert tmpl1 is not tmpl3

    @pytest.mark.parametrize('encoding, expected_text', [
        ('utf-8', u'tech'),
        ('utf-16', u'整档'),
    ])
    def test_uses_specified_encoding(self, encoding, expected_text):
        filesystem_loader = loaders.FileSystemLoader(self.searchpath, encoding=encoding)
        env = Environment(loader=filesystem_loader)
        tmpl = env.get_template('variable_encoding.txt')
        assert tmpl.render().strip() == expected_text


@pytest.mark.loaders
@pytest.mark.moduleloader
class TestModuleLoader(object):
    archive = None

    def compile_down(self, prefix_loader, zip='deflated', py_compile=False):
        log = []
        self.reg_env = Environment(loader=prefix_loader)
        if zip is not None:
            fd, self.archive = tempfile.mkstemp(suffix='.zip')
            os.close(fd)
        else:
            self.archive = tempfile.mkdtemp()
        self.reg_env.compile_templates(self.archive, zip=zip,
                                       log_function=log.append,
                                       py_compile=py_compile)
        self.mod_env = Environment(loader=loaders.ModuleLoader(self.archive))
        return ''.join(log)

    def teardown(self):
        if hasattr(self, 'mod_env'):
            if os.path.isfile(self.archive):
                os.remove(self.archive)
            else:
                shutil.rmtree(self.archive)
            self.archive = None

    def test_log(self, prefix_loader):
        log = self.compile_down(prefix_loader)
        assert 'Compiled "a/foo/test.html" as ' \
               'tmpl_a790caf9d669e39ea4d280d597ec891c4ef0404a' in log
        assert 'Finished compiling templates' in log
        assert 'Could not compile "a/syntaxerror.html": ' \
               'Encountered unknown tag \'endif\'' in log

    def _test_common(self):
        tmpl1 = self.reg_env.get_template('a/test.html')
        tmpl2 = self.mod_env.get_template('a/test.html')
        assert tmpl1.render() == tmpl2.render()

        tmpl1 = self.reg_env.get_template('b/justdict.html')
        tmpl2 = self.mod_env.get_template('b/justdict.html')
        assert tmpl1.render() == tmpl2.render()

    def test_deflated_zip_compile(self, prefix_loader):
        self.compile_down(prefix_loader, zip='deflated')
        self._test_common()

    def test_stored_zip_compile(self, prefix_loader):
        self.compile_down(prefix_loader, zip='stored')
        self._test_common()

    def test_filesystem_compile(self, prefix_loader):
        self.compile_down(prefix_loader, zip=None)
        self._test_common()

    def test_weak_references(self, prefix_loader):
        self.compile_down(prefix_loader)
        tmpl = self.mod_env.get_template('a/test.html')
        key = loaders.ModuleLoader.get_template_key('a/test.html')
        name = self.mod_env.loader.module.__name__

        assert hasattr(self.mod_env.loader.module, key)
        assert name in sys.modules

        # unset all, ensure the module is gone from sys.modules
        self.mod_env = tmpl = None

        try:
            import gc
            gc.collect()
        except:
            pass

        assert name not in sys.modules

    # This test only makes sense on non-pypy python 2
    @pytest.mark.skipif(
        not (PY2 and not PYPY),
        reason='This test only makes sense on non-pypy python 2')
    def test_byte_compilation(self, prefix_loader):
        log = self.compile_down(prefix_loader, py_compile=True)
        assert 'Byte-compiled "a/test.html"' in log
        tmpl1 = self.mod_env.get_template('a/test.html')
        mod = self.mod_env.loader.module. \
            tmpl_3c4ddf650c1a73df961a6d3d2ce2752f1b8fd490
        assert mod.__file__.endswith('.pyc')

    def test_choice_loader(self, prefix_loader):
        log = self.compile_down(prefix_loader)

        self.mod_env.loader = loaders.ChoiceLoader([
            self.mod_env.loader,
            loaders.DictLoader({'DICT_SOURCE': 'DICT_TEMPLATE'})
        ])

        tmpl1 = self.mod_env.get_template('a/test.html')
        assert tmpl1.render() == 'BAR'
        tmpl2 = self.mod_env.get_template('DICT_SOURCE')
        assert tmpl2.render() == 'DICT_TEMPLATE'

    def test_prefix_loader(self, prefix_loader):
        log = self.compile_down(prefix_loader)

        self.mod_env.loader = loaders.PrefixLoader({
            'MOD':      self.mod_env.loader,
            'DICT':     loaders.DictLoader({'test.html': 'DICT_TEMPLATE'})
        })

        tmpl1 = self.mod_env.get_template('MOD/a/test.html')
        assert tmpl1.render() == 'BAR'
        tmpl2 = self.mod_env.get_template('DICT/test.html')
        assert tmpl2.render() == 'DICT_TEMPLATE'

    @pytest.mark.skipif(PY2, reason='pathlib is not available in Python 2')
    def test_path_as_pathlib(self, prefix_loader):
        self.compile_down(prefix_loader)

        mod_path = self.mod_env.loader.module.__path__[0]

        import pathlib
        mod_loader = loaders.ModuleLoader(pathlib.Path(mod_path))
        self.mod_env = Environment(loader=mod_loader)

        self._test_common()

    @pytest.mark.skipif(PY2, reason='pathlib is not available in Python 2')
    def test_supports_pathlib_in_list_of_paths(self, prefix_loader):
        self.compile_down(prefix_loader)

        mod_path = self.mod_env.loader.module.__path__[0]

        import pathlib
        mod_loader = loaders.ModuleLoader([
            pathlib.Path(mod_path),
            '/tmp/templates'
        ])
        self.mod_env = Environment(loader=mod_loader)

        self._test_common()


@pytest.fixture()
def package_dir_loader(monkeypatch):
    monkeypatch.syspath_prepend(os.path.dirname(__file__))
    return PackageLoader("res")


@pytest.mark.parametrize(
    ("template", "expect"), [("foo/test.html", "FOO"), ("test.html", "BAR")]
)
def test_package_dir_source(package_dir_loader, template, expect):
    source, name, up_to_date = package_dir_loader.get_source(None, template)
    assert source.rstrip() == expect
    assert name.endswith(os.path.join(*split_template_path(template)))
    assert up_to_date()


def test_package_dir_list(package_dir_loader):
    templates = package_dir_loader.list_templates()
    assert "foo/test.html" in templates
    assert "test.html" in templates


@pytest.fixture()
def package_zip_loader(monkeypatch):
    monkeypatch.syspath_prepend(
        os.path.join(os.path.dirname(__file__), "res", "package.zip")
    )
    return PackageLoader("t_pack")


@pytest.mark.parametrize(
    ("template", "expect"), [("foo/test.html", "FOO"), ("test.html", "BAR")]
)
def test_package_zip_source(package_zip_loader, template, expect):
    source, name, up_to_date = package_zip_loader.get_source(None, template)
    assert source.rstrip() == expect
    assert name.endswith(os.path.join(*split_template_path(template)))
    assert up_to_date is None


@pytest.mark.xfail(
    PYPY,
    reason="PyPy's zipimporter doesn't have a _files attribute.",
    raises=TypeError,
)
def test_package_zip_list(package_zip_loader):
    assert package_zip_loader.list_templates() == ["foo/test.html", "test.html"]
