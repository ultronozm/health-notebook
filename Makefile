PYTHON ?= python3
NOTEBOOK ?= $(HOME)/health-notebook

.PHONY: test test-glucose site demo

test:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m unittest tools.site.test_build_site -v
	@for script in scripts/*.sh; do bash -n "$$script" || exit; done

test-glucose:
	.venv/bin/python -m unittest tools.librelinkup.test_fetch_glucose -v

site:
	$(PYTHON) tools/site/build_site.py --repo "$(NOTEBOOK)"

demo:
	$(PYTHON) tools/site/build_site.py --repo examples/notebook --today 2026-01-15
