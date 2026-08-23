
    def _stamp_waiter(self):
        # Attribution follows the table: a waiter claims it once with their PIN and
        # every order and invoice on that table is theirs without asking again.
        if not self.get("waiter") and self.table:
            self.waiter = frappe.db.get_value("Restaurant Object", self.table, "waiter")

    def insert(self, *args, **kwargs):
        self._stamp_waiter()
        return super().insert(*args, **kwargs)

    def save(self, *args, **kwargs):
        self._stamp_waiter()
        return super().save(*args, **kwargs)
