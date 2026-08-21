/* menu-item-editor (patch layer): create and edit menu items straight from the
   Menu Management screen. All writes go through
   restaurant_management.api.upsert_menu_item -> Item / Item Price / Restaurant
   Menu, so frappe remains the system of record. */
(() => {
  const API = "restaurant_management.api.";

  function editor_dialog(values, on_done) {
    const is_new = !values.name;
    const fields = [
      { fieldname: "item_name", fieldtype: "Data", label: __("Name"), reqd: 1, default: values.item_name },
      {
        fieldname: "item_group", fieldtype: "Link", options: "Item Group", label: __("Category"), reqd: 1,
        default: values.item_group, get_query: () => ({ filters: { is_group: 0 } })
      },
      { fieldname: "rate", fieldtype: "Currency", label: __("Price"), default: values.rate },
      {
        fieldname: "item_type", fieldtype: "Select", options: "Veg\nNon-Veg", label: __("Type"),
        default: values.item_type || "Veg"
      },
      { fieldname: "image", fieldtype: "Attach Image", label: __("Photo"), default: values.image },
    ];
    if (is_new) {
      fields.push({ fieldname: "add_to_menu", fieldtype: "Check", label: __("Show on the menu"), default: 1 });
    }
    const d = new frappe.ui.Dialog({
      title: is_new ? __("New Menu Item") : __("Edit {0}", [values.item_name || values.name]),
      fields,
      primary_action_label: is_new ? __("Create") : __("Save"),
      primary_action(v) {
        frappe.call({
          method: API + "upsert_menu_item",
          args: Object.assign({ item_code: values.name || null }, v),
          freeze: true,
        }).then(r => {
          d.hide();
          frappe.show_alert({ message: __("Saved {0}", [r.message]), indicator: "green" });
          on_done && on_done(r.message);
        });
      },
    });
    d.show();
  }

  function reload_menu_items() {
    const mm = window.__rm_menu_manage;
    const tree = mm && mm.storage && mm.storage();
    const im = tree && tree.current_item_manage;
    im && im.load_items_data && im.load_items_data();
  }

  if (typeof MenuManage !== "undefined") {
    const _make_items = MenuManage.prototype.make_items;
    MenuManage.prototype.make_items = function () {
      window.__rm_menu_manage = this;
      _make_items.call(this);
      setTimeout(() => {
        const host = this.item_type_wrapper && this.item_type_wrapper.JQ && this.item_type_wrapper.JQ();
        if (!host || !host.length || host.find(".rm-new-item").length) return;
        $(`<button class="btn btn-primary btn-sm rm-new-item"
                   style="margin-left:8px; border-radius:20px; white-space:nowrap;">
             <span class="fa fa-plus"></span> ${__("New Item")}</button>`)
          .appendTo(host.find(".input-group").first())
          .on("click", () => editor_dialog({}, reload_menu_items));
      }, 300);
    };
  }

  // edit an existing item: tap its price pill on a Menu Management card
  $(document).on("click", '[id^="items-container-menu-manage"] .small-box.item .btn-secondary', function (e) {
    e.preventDefault();
    e.stopPropagation();
    const code = $(this).closest(".small-box.item").attr("item-code");
    if (!code) return;
    frappe.call({ method: API + "get_menu_item", args: { item_code: code } })
      .then(r => editor_dialog(r.message, reload_menu_items));
  });
})();
