
    def _stamp_waiter(self):
        # Service details follow the table: the waiter claims it once with a PIN,
        # and the party size recorded at seating shouldn't be typed a second time.
        if not self.get("waiter") and self.table:
            self.waiter = frappe.db.get_value("Restaurant Object", self.table, "waiter")

        if not self.get("dinners") and self.table:
            self.dinners = frappe.db.get_value(
                "Restaurant Booking",
                {"table": self.table, "status": "Open"},
                "no_of_people",
                order_by="creation desc",
            ) or 0

    def insert(self, *args, **kwargs):
        self._stamp_waiter()
        return super().insert(*args, **kwargs)

    def save(self, *args, **kwargs):
        self._stamp_waiter()
        return super().save(*args, **kwargs)
