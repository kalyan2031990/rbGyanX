"""
Versioned reference packs for the literature quick-compare.

A pack is a JSON file with ``pack_id``, ``pack_version`` and ``entries``; each entry carries
organ, endpoint, metric, value, units and a citation. Packs are additive: a site can drop its
own file into this directory and it will be loaded alongside the shipped ones.

That is deliberate. rbGyanX is installed in many countries and under many protocols, so
asserting one institution's tolerances as universal would be wrong. The shipped packs are
orientation values with citations, not a plan-acceptance standard.

This is a package (rather than a bare directory) so the JSON ships in a wheel - see
``[tool.setuptools.package-data]`` in pyproject.toml.
"""
