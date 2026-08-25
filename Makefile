# Deploying the restaurant POS. Run these on the server unless a target says local.
#   make status | backup | deploy | test-server | clean-tests | rollback

SHELL := /bin/bash
SITE  ?= $(shell sed -n 's/^FRAPPE_SITE_NAME_HEADER=//p' .env 2>/dev/null | tail -1)
TAG   ?= $(shell sed -n 's/^erpnext=//p' restaurant/PINNED_APPS 2>/dev/null)
IMAGE := custom-erpnext:$(TAG)
BE     = $$(docker compose ps -q backend)
APPDIR = /home/frappe/frappe-bench/apps/restaurant_management/restaurant_management
TARBALL ?= pos-$(TAG).tgz
HOST  ?=

.PHONY: help status backup deploy deploy-loaded redeploy test test-server clean-tests save ship rollback

help:
	@echo "SITE=$(SITE)  IMAGE=$(IMAGE)"
	@echo
	@echo "  make status        what is running, which versions, queue depth"
	@echo "  make backup        database + files, before anything else"
	@echo "  make deploy        move to the pinned versions (builds here, needs ~4GB RAM free)"
	@echo "  make deploy-loaded same, but uses an image already loaded (make ship)"
	@echo "  make redeploy      same versions, rebake the restaurant patches only"
	@echo "  make test-server   floor + staff suites (they clean up; safe on a live site)"
	@echo "  make test          adds the browser suites (they seat parties — after close)"
	@echo "  make clean-tests   remove anything a test run left behind"
	@echo "  make rollback      how to go back"
	@echo
	@echo "  on your own machine:  make save && make ship HOST=user@server"

status:
	@echo "== containers =="; docker compose ps --format '{{.Service}}\t{{.Image}}\t{{.Status}}' 2>/dev/null | head -8
	@echo "== apps =="; docker compose exec -T backend bench --site $(SITE) list-apps 2>/dev/null | tail -5
	@echo "== queues =="; echo 'from frappe.utils.background_jobs import get_queue; print("pending:", {q: len(get_queue(q)) for q in ["short","default","long"]})' \
		| docker compose exec -T backend bench --site $(SITE) console 2>/dev/null | grep pending
	@echo "== disk =="; df -h . | tail -1

backup:
	docker compose exec -T backend bench --site $(SITE) backup --with-files

deploy:
	SITE=$(SITE) ./restaurant/upgrade.sh

deploy-loaded:
	SITE=$(SITE) SKIP_BUILD=1 ./restaurant/upgrade.sh

redeploy:
	SITE=$(SITE) ./restaurant/redeploy.sh

test-server:
	@for suite in turn_test staff_test; do \
		echo "== $$suite =="; \
		docker cp restaurant/e2e/$$suite.py "$(BE)":$(APPDIR)/$$suite.py >/dev/null; \
		echo "exec(open('$(APPDIR)/$$suite.py').read(), globals()); run()" \
			| docker compose exec -T backend bench --site $(SITE) console 2>&1 \
			| grep -E 'PASS|FAIL|passed' | tail -20; \
	done

test: test-server
	cd restaurant/e2e && [ -d node_modules ] || npm i --no-audit --no-fund
	SITE=$(SITE) BASE=https://$(SITE) ./restaurant/e2e/run-all.sh

clean-tests:
	docker cp restaurant/e2e/cleanup.py "$(BE)":$(APPDIR)/cleanup.py >/dev/null
	@echo "exec(open('$(APPDIR)/cleanup.py').read(), globals()); run()" \
		| docker compose exec -T backend bench --site $(SITE) console 2>&1 | grep -E 'removed:|KEPT'

# --- run these on your own machine ---
save:
	docker save $(IMAGE) | gzip -1 > $(TARBALL)
	@ls -lh $(TARBALL) | awk '{print "wrote", $$9, $$5}'

ship:
	@[ -n "$(HOST)" ] || { echo "HOST=user@server is required"; exit 1; }
	@# --bwlimit keeps a flaky link from breaking the pipe; /tmp because the
	@# deploy account may have no home directory
	rsync --append-verify --partial --bwlimit=2500 --timeout=300 -P \
		-e 'ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=8' \
		$(TARBALL) $(HOST):/tmp/$(TARBALL)
	ssh $(HOST) 'gunzip -c /tmp/$(TARBALL) | docker load && rm -f /tmp/$(TARBALL)'

rollback:
	@echo "1. restore the env that named the old image:"
	@echo "     cp .env.before-$(TAG) .env && docker compose up -d"
	@echo "2. if the data must go back too, pick a backup and restore it:"
	@echo "     docker compose exec -T backend ls -t sites/$(SITE)/private/backups | head"
	@echo "     docker compose exec -T backend bench --site $(SITE) restore <file>"
	@echo "   the previous image is still on this machine; nothing prunes it for you"
