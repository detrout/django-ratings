#!/usr/bin/env python
import os
import sys

from os.path import dirname, abspath

from django.conf import settings
import django

if not settings.configured:
    #os.environ['DJANGO_SETTINGS_MODULE'] = 'djangoratings.default_settings'
    settings.configure(
        SECRET_KEY='lkaulkbjakla',
        DEBUG=True,
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': 'djangoratings',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'djangoratings',
            'tests',
        ]
    )

from django.test.utils import get_runner


def runtests(*test_args):
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['tests.tests'])
    sys.exit(bool(failures))


if __name__ == '__main__':
    runtests(*sys.argv[1:])
