# This empty CleanSpec.mk file will prevent the build system
# from descending into subdirs.
#
$(call add-clean-step, rm -rf $(OUT_DIR)/host/linux-x86/bin/audit2allow)
$(call add-clean-step, rm -rf $(OUT_DIR)/host/linux-x86/bin/audit2why)
$(call add-clean-step, rm -rf $(PRODUCT_OUT)/vendor/lib/libselinux.so)
