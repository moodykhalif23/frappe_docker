
    def _party(self):
        if not self.get("booking"):
            return None
        return frappe.db.get_value(
            "Restaurant Booking", self.booking,
            ["name", "customer", "no_of_people", "waiter", "status"], as_dict=True)

    def _stamp_waiter(self):
        # Service details follow the party, not the table: two waiters can share
        # a six-top and each keeps the covers they served.
        party = self._party()

        if not self.get("waiter"):
            self.waiter = (party.waiter if party else None) or (
                frappe.db.get_value("Restaurant Object", self.table, "waiter")
                if self.table else None)

        if not self.get("dinners"):
            self.dinners = (party.no_of_people if party else None) or (
                frappe.db.get_value(
                    "Restaurant Booking",
                    {"table": self.table, "status": "Open"},
                    "no_of_people",
                    order_by="creation desc",
                ) if self.table else None) or 0

    def insert(self, *args, **kwargs):
        self._stamp_waiter()
        return super().insert(*args, **kwargs)

    def save(self, *args, **kwargs):
        self._stamp_waiter()
        return super().save(*args, **kwargs)
