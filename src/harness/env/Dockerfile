# Hermetic environment for running the django test suite.
#
# The django source is NOT baked in -- a per-task git worktree is bind-mounted
# at /testbed at run time, so one image serves every task. Only the test
# dependencies live here, pinned so the image is reproducible independently of
# which commit a task pins.
#
# django itself is not pip-installed. `python tests/runtests.py` puts only
# /testbed/tests on sys.path (script dir), not /testbed, so `import django`
# needs PYTHONPATH -- set below. This is preferred over `pip install -e .`
# because it writes nothing into the mounted worktree: an egg-info directory
# would show up in the `git diff` used to extract the model's patch, and the
# install would need network access at eval time.
#
# Scope limit: GDAL/GEOS are deliberately absent, so gis_tests cannot run in
# this image. Mining must exclude django/contrib/gis (see mining.yaml).

FROM python:3.13-slim-bookworm

# /testbed  -- the bind-mounted django worktree, so `import django` resolves.
# /harness  -- read-only mount holding the injected settings + result collector.
# PYTHONHASHSEED=0 disables hash randomization, which python enables per process
# by default (django does not pin it). Without this, dict/set iteration order
# varies between runs, so grading the same (task, patch) twice could in principle
# disagree. Pinning it makes a verdict reproducible by construction rather than
# something validation has to sample for by re-running.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/testbed:/harness \
    PYTHONHASHSEED=0

# gcc + libmemcached-dev are build-time requirements of pylibmc; libmemcached11
# and libpq5 are needed at run time. Kept in one layer to avoid a fat image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        libmemcached-dev \
        zlib1g-dev \
        libjpeg62-turbo-dev \
    && rm -rf /var/lib/apt/lists/*

# Pinned test dependencies. Mirrors django's tests/requirements/py3.txt with
# two deliberate omissions:
#   - selenium: browser tests only run under --selenium, which this harness
#     never passes; the package is unused weight.
#   - pywatchman: only exercised by autoreload tests that skip without a
#     running watchman daemon.
# Both omissions cause skips, never failures. parse.py counts a skip as
# neither pass nor fail, so they cannot silently affect a grade.
RUN pip install \
        "asgiref==3.12.1" \
        "sqlparse==0.5.3" \
        "tzdata==2025.2" \
        "aiosmtpd==1.4.6" \
        "argon2-cffi==23.1.0" \
        "bcrypt==4.2.1" \
        "black==26.5.1" \
        "docutils==0.22" \
        "geoip2==4.8.1" \
        "jinja2==3.1.5" \
        "numpy==2.2.1" \
        "Pillow==11.1.0" \
        "pylibmc==1.6.3" \
        "pymemcache==4.0.0" \
        "PyYAML==6.0.2" \
        "redis==5.2.1" \
        "tblib==3.0.0"

WORKDIR /testbed

# Grading always passes an explicit command; this default only makes the image
# useful to poke at by hand.
CMD ["python", "tests/runtests.py", "--settings=test_sqlite", "--parallel", "1"]
