"""Code shared by every data source: caching, output, configuration, errors, CLI plumbing.

Nothing in here knows about a particular API. Each source package
(:mod:`dismal.bls`, :mod:`dismal.bea`, :mod:`dismal.fred`) builds on these
modules and adds its own client, models, periods, records and commands.
"""
