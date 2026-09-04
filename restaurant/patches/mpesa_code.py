# Paying by M-Pesa recorded nothing but an amount: the customer's confirmation
# code was read off the phone and lost. The pay form now asks for it beside the
# M-Pesa amount, refuses to pay without a well-formed one, and sends it as the
# payment row's reference — so a report can tie every M-Pesa shilling to a code.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"

src = open(P).read()

# upgrade: the refusal was a dialog, and closing it took the pay form down with it
OLD_DIALOG = """      frappe.msgprint({ title: __("M-Pesa code"), indicator: "red",
        message: __("Enter the customer's {0} confirmation code — 10 letters and digits, as on their phone.", [short]) });
"""
TOAST = """      // a toast, not a dialog: closing a dialog here takes the pay form down with it
      frappe.show_alert({ indicator: "red",
        message: __("Enter the customer's {0} confirmation code — 10 letters and digits, as on their phone.", [short]) }, 7);
"""
if OLD_DIALOG in src:
    src = src.replace(OLD_DIALOG, TOAST, 1)
BAD_HANDLER = """        this.payment_refs[mode_of_payment.mode_of_payment] = frappe.jshtml({
          tag: "input",
          properties: { type: "text", class: "input-with-feedback form-control bold rm-mpesa-code",
                        placeholder: __("M-Pesa confirmation code"), maxlength: 12,
                        autocapitalize: "characters", spellcheck: "false" },
        }).on(["change", "keyup"], (obj) => { obj.val(String(obj.val() || "").toUpperCase().replace(/[^A-Z0-9]/g, "")); });
        payment_methods += this.form_tag(__("M-Pesa code"), this.payment_refs[mode_of_payment.mode_of_payment]);"""
GOOD_HANDLER = """        const ref = frappe.jshtml({
          tag: "input",
          properties: { type: "text", class: "input-with-feedback form-control bold rm-mpesa-code",
                        placeholder: __("M-Pesa confirmation code"), maxlength: 12,
                        autocapitalize: "characters", spellcheck: "false" },
        });
        // jshtml caches val() after its first read: read and write the element itself
        ref.on(["change", "keyup"], () => {
          const code = String(ref.JQ().val() || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
          ref.JQ().val(code); ref.value = code;
        });
        this.payment_refs[mode_of_payment.mode_of_payment] = ref;
        payment_methods += this.form_tag(__("M-Pesa code"), ref);"""
if BAD_HANDLER in src:
    open(P, "w").write(src.replace(BAD_HANDLER, GOOD_HANDLER, 1))
    print("mpesa code: code input handler upgraded")
    raise SystemExit
CACHED_HANDLER = """        // change/keyup callbacks get no element: use the handle
        ref.on(["change", "keyup"], () => { ref.val(String(ref.val() || "").toUpperCase().replace(/[^A-Z0-9]/g, "")); });"""
DOM_HANDLER = """        // jshtml caches val() after its first read: read and write the element itself
        ref.on(["change", "keyup"], () => {
          const code = String(ref.JQ().val() || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
          ref.JQ().val(code); ref.value = code;
        });"""
CACHED_REF = """      const code = String(this.payment_refs[mode].val() || "").trim().toUpperCase();"""
DOM_REF = """      const code = String(this.payment_refs[mode].JQ().val() || "").trim().toUpperCase();"""
if CACHED_HANDLER in src or CACHED_REF in src:
    open(P, "w").write(src.replace(CACHED_HANDLER, DOM_HANDLER, 1).replace(CACHED_REF, DOM_REF, 1))
    print("mpesa code: code input reads the element, not jshtml's cache")
    raise SystemExit
NO_RESET = TOAST + "      if (this.payment_refs[short]) this.payment_refs[short].select();\n"
if NO_RESET in src:
    open(P, "w").write(src.replace(NO_RESET, TOAST + "      this.reset_payment_button();  // the click disabled it; give it back\n      if (this.payment_refs[short]) this.payment_refs[short].select();\n", 1))
    print("mpesa code: refusal upgraded — toast, button given back")
    raise SystemExit
if "rm_mpesa_code" in src:
    print("mpesa code: already applied")
    raise SystemExit

# 1. an extra input under an M-Pesa amount
OLD = """      payment_methods += this.form_tag(
        mode_of_payment.mode_of_payment, this.payment_methods[mode_of_payment.mode_of_payment]
      );
    });
"""
NEW = """      payment_methods += this.form_tag(
        mode_of_payment.mode_of_payment, this.payment_methods[mode_of_payment.mode_of_payment]
      );
      // rm_mpesa_code: the customer's confirmation code rides with the amount
      if (/m-?pesa/i.test(mode_of_payment.mode_of_payment)) {
        this.payment_refs = this.payment_refs || {};
        const ref = frappe.jshtml({
          tag: "input",
          properties: { type: "text", class: "input-with-feedback form-control bold rm-mpesa-code",
                        placeholder: __("M-Pesa confirmation code"), maxlength: 12,
                        autocapitalize: "characters", spellcheck: "false" },
        });
        // jshtml caches val() after its first read: read and write the element itself
        ref.on(["change", "keyup"], () => {
          const code = String(ref.JQ().val() || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
          ref.JQ().val(code); ref.value = code;
        });
        this.payment_refs[mode_of_payment.mode_of_payment] = ref;
        payment_methods += this.form_tag(__("M-Pesa code"), ref);
      }
    });
"""
if src.count(OLD) != 1:
    raise SystemExit("mpesa code: make_inputs anchor found %d times" % src.count(OLD))
src = src.replace(OLD, NEW, 1)

# 2. the codes travel as `references`, keyed like the amounts
OLD = """  send_payment() {
    RM.working("Saving Invoice");
    this.#send_payment();
  }
"""
NEW = """  get payment_references() {
    const refs = {};
    Object.keys(this.payment_refs || {}).forEach((mode) => {
      const code = String(this.payment_refs[mode].JQ().val() || "").trim().toUpperCase();
      if (code) refs[mode] = code;
    });
    return refs;
  }

  // M-Pesa money needs its code before anything is saved: ten letters and digits.
  mpesa_code_missing() {
    const amounts = this.payments_values;
    return Object.keys(this.payment_refs || {}).find((mode) =>
      amounts[mode] > 0 && !/^[A-Z0-9]{10}$/.test(this.payment_references[mode] || ""));
  }

  send_payment() {
    const short = this.mpesa_code_missing();
    if (short) {
      // a toast, not a dialog: closing a dialog here takes the pay form down with it
      frappe.show_alert({ indicator: "red",
        message: __("Enter the customer's {0} confirmation code — 10 letters and digits, as on their phone.", [short]) }, 7);
      this.reset_payment_button();  // the click disabled it; give it back
      if (this.payment_refs[short]) this.payment_refs[short].select();
      return;
    }
    RM.working("Saving Invoice");
    this.#send_payment();
  }
"""
if src.count(OLD) != 1:
    raise SystemExit("mpesa code: send_payment anchor found %d times" % src.count(OLD))
src = src.replace(OLD, NEW, 1)

OLD = """          args: {
            mode_of_payment: this.payments_values
          },"""
NEW = """          args: {
            mode_of_payment: this.payments_values,
            references: this.payment_references,
          },"""
if src.count(OLD) != 1:
    raise SystemExit("mpesa code: make_invoice args anchor found %d times" % src.count(OLD))
src = src.replace(OLD, NEW, 1)
open(P, "w").write(src)
print("mpesa code: the pay form asks for the confirmation code and sends it")
