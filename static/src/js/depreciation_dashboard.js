/** @odoo-module **/

import { Component, onWillStart, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DepreciationDashboard extends Component {
    static template = "kio_asset_management.DepreciationDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        const context = (this.props.action && this.props.action.context) || {};
        const sourceAssetId = context.active_asset_id || context.asset_id || context.depreciation_asset_id || false;
        this.state = useState({
            loaded: false,
            selectedAssetId: sourceAssetId,
            lockedAssetId: context.lock_asset_selection ? sourceAssetId : false,
            assetSelectionLocked: Boolean(context.lock_asset_selection && sourceAssetId),
            data: this.emptyData(),
            summaryEditMode: false,
            summaryForm: this.emptySummaryForm(),
            summaryErrors: {},
            summaryDriverField: "depreciableAmount",
            summaryMessage: "",
            configModalOpen: false,
            configForm: this.emptyConfigForm(),
            configError: "",
            configSaving: false,
        });
        onWillStart(async () => this.loadData(this.state.selectedAssetId));
        useExternalListener(window, "keydown", (event) => this.onWindowKeydown(event));
    }

    emptyData() {
        return {
            assetOptions: [],
            methodOptions: [],
            fiscalYearOptions: [],
            journalOptions: [],
            expenseAccountOptions: [],
            accumulatedAccountOptions: [],
            filters: {},
            assetInfo: {},
            summary: {},
            summaryInputs: {},
            progress: {},
            scheduleRows: [],
            totals: {},
            automation: {},
            configuration: {},
            preview: {},
            emptyMessage: "",
        };
    }

    emptySummaryForm() {
        return {
            depreciationMethod: "straight_line",
            usefulLifeYears: "",
            depreciationStartDate: "",
            residualValue: "",
            annualDepreciation: "",
            monthlyDepreciation: "",
            depreciableAmount: "",
        };
    }

    emptyConfigForm() {
        return {
            depreciationJournalId: "",
            depreciationExpenseAccountId: "",
            accumulatedDepreciationAccountId: "",
            createJournal: "monthly",
            autoCreate: false,
            nextRunDate: "",
            postDueEntriesAutomatically: true,
        };
    }

    get selectedAssetLabel() {
        const assetId = Number(this.state.selectedAssetId) || false;
        const asset = ((this.state.data && this.state.data.assetOptions) || []).find((item) => item.id === assetId);
        return asset ? asset.label : "";
    }

    get scheduleTableRows() {
        return ((this.state.data && this.state.data.scheduleRows) || []).filter((row) => row.journalEntryId);
    }

    get showScheduleTotals() {
        const rows = (this.state.data && this.state.data.scheduleRows) || [];
        return Boolean(rows.length) && rows.every((row) => row.journalEntryId);
    }

    async loadData(assetId = false, options = {}) {
        const requestedAssetId = this.state.assetSelectionLocked ? this.state.lockedAssetId : assetId;
        const data = await this.orm.call("kio.asset.dashboard.service", "get_depreciation_dashboard_data", [requestedAssetId || false]);
        this.state.data = data || this.emptyData();
        this.state.selectedAssetId = this.state.data.selectedAssetId || false;
        if (this.state.assetSelectionLocked) {
            this.state.lockedAssetId = this.state.selectedAssetId || this.state.lockedAssetId;
            this.state.data.assetOptions = (this.state.data.assetOptions || []).filter((asset) => asset.id === this.state.lockedAssetId);
        }
        this.resetSummaryForm();
        this.resetConfigForm();
        this.state.summaryEditMode = false;
        this.state.summaryErrors = {};
        if (!options.keepMessage) {
            this.state.summaryMessage = "";
        }
        this.state.loaded = true;
    }

    onAssetChange(event) {
        if (this.state.assetSelectionLocked) {
            event.target.value = this.state.lockedAssetId || this.state.selectedAssetId || "";
            return;
        }
        const assetId = Number(event.target.value) || false;
        this.loadData(assetId);
    }

    onMethodChange(event) {
        this.state.data.filters.method = event.target.value;
    }

    onFiscalYearChange(event) {
        this.state.data.filters.fiscalYear = event.target.value;
    }

    openDepreciationDatePicker(event) {
        const target = event.currentTarget;
        const wrapper = target.closest ? target.closest(".kio_depr_date") : null;
        const input = target.matches && target.matches("input") ? target : wrapper && wrapper.querySelector("input[type='date']");
        if (!input) {
            return;
        }
        input.focus();
        if (typeof input.showPicker === "function") {
            try {
                input.showPicker();
            } catch {
                // Focusing the date input still lets the browser handle unsupported picker calls.
            }
        }
    }

    onWindowKeydown(event) {
        if (event.key === "Escape" && this.state.configModalOpen && !this.state.configSaving) {
            this.closeConfigurationModal();
        }
    }

    onFromDateChange(event) {
        this.state.data.filters.fromDate = event.target.value;
    }

    onToDateChange(event) {
        this.state.data.filters.toDate = event.target.value;
    }

    async onAutoCreateChange(event) {
        this.state.data.automation.autoCreate = event.target.checked;
        await this.saveAutomationSettings();
    }

    async onCreateJournalChange(event) {
        this.state.data.automation.createJournal = event.target.value;
        await this.saveAutomationSettings();
    }

    onNextRunDateChange(event) {
        this.state.data.automation.nextRunDate = event.target.value;
    }

    async onJournalChange(event) {
        this.state.data.automation.journalId = Number(event.target.value) || false;
        await this.saveAutomationSettings();
    }

    async saveAutomationSettings() {
        const automation = this.state.data.automation || {};
        const result = await this.orm.call("kio.asset.dashboard.service", "update_depreciation_automation", [this.state.selectedAssetId || false, {
            autoCreate: automation.autoCreate,
            createJournal: automation.createJournal,
            nextRunDate: automation.nextRunDate || false,
            journalId: automation.journalId || false,
        }]);
        this.applyDashboardResult(result);
    }

    applyDashboardResult(result, fallbackMessage = "") {
        if (!result) {
            return;
        }
        if (result.selectedAssetId) {
            this.state.data = result;
            this.state.selectedAssetId = result.selectedAssetId;
            if (this.state.assetSelectionLocked) {
                this.state.lockedAssetId = this.state.selectedAssetId || this.state.lockedAssetId;
                this.state.data.assetOptions = (this.state.data.assetOptions || []).filter((asset) => asset.id === this.state.lockedAssetId);
            }
            this.resetSummaryForm();
            this.resetConfigForm();
            this.state.summaryEditMode = false;
            this.state.summaryErrors = {};
        }
        this.state.summaryMessage = result.message || fallbackMessage || "";
    }

    resetConfigForm() {
        const config = (this.state.data && this.state.data.configuration) || {};
        this.state.configForm = {
            depreciationJournalId: config.depreciationJournalId ? String(config.depreciationJournalId) : "",
            depreciationExpenseAccountId: config.depreciationExpenseAccountId ? String(config.depreciationExpenseAccountId) : "",
            accumulatedDepreciationAccountId: config.accumulatedDepreciationAccountId ? String(config.accumulatedDepreciationAccountId) : "",
            createJournal: config.createJournal || "monthly",
            autoCreate: Boolean(config.autoCreate),
            nextRunDate: config.nextRunDate || "",
            postDueEntriesAutomatically: config.postDueEntriesAutomatically !== false,
        };
        this.state.configError = "";
    }

    openConfigurationModal() {
        this.resetConfigForm();
        this.state.configModalOpen = true;
    }

    closeConfigurationModal() {
        if (this.state.configSaving) {
            return;
        }
        this.state.configModalOpen = false;
        this.state.configError = "";
    }

    onConfigFieldChange(fieldName, event) {
        this.state.configError = "";
        this.state.configForm[fieldName] = event.target.value || "";
    }

    onConfigBooleanChange(fieldName, event) {
        this.state.configError = "";
        this.state.configForm[fieldName] = Boolean(event.target.checked);
    }

    validateConfigForm() {
        return Boolean(this.state.configForm.depreciationExpenseAccountId);
    }

    async saveConfiguration() {
        const validationMessage = "Please select the Depreciation Expense Account.";
        if (!this.validateConfigForm()) {
            this.state.configError = validationMessage;
            return;
        }
        this.state.configSaving = true;
        this.state.configError = "";
        try {
            const form = this.state.configForm;
            const result = await this.orm.call("kio.asset.dashboard.service", "update_depreciation_configuration", [this.state.selectedAssetId || false, {
                depreciationExpenseAccountId: Number(form.depreciationExpenseAccountId) || false,
            }]);
            if (!result || !result.success) {
                this.state.configError = (result && result.message) || validationMessage;
                return;
            }
            this.applyDashboardResult(result, result.message || "Depreciation configuration saved successfully.");
            this.resetConfigForm();
            this.state.configModalOpen = false;
            this.notification.add(result.message || "Depreciation configuration saved successfully.", { type: "success" });
        } catch (error) {
            console.error("Could not save depreciation configuration", error);
            this.state.configError = (error && error.data && error.data.message) || (error && error.message) || validationMessage;
        } finally {
            this.state.configSaving = false;
        }
    }

    resetSummaryForm() {
        const inputs = this.state.data.summaryInputs || {};
        this.state.summaryForm = {
            depreciationMethod: inputs.depreciationMethod || "straight_line",
            usefulLifeYears: this.numberToInput(inputs.usefulLifeYears),
            depreciationStartDate: inputs.depreciationStartDate || "",
            residualValue: this.decimalToInput(inputs.residualValue),
            annualDepreciation: this.decimalToInput(inputs.annualDepreciation),
            monthlyDepreciation: this.decimalToInput(inputs.monthlyDepreciation),
            depreciableAmount: this.decimalToInput(inputs.depreciableAmount),
        };
        this.state.summaryDriverField = "depreciableAmount";
    }

    numberToInput(value) {
        return value === undefined || value === null || value === false ? "" : String(value);
    }

    decimalToInput(value) {
        if (value === undefined || value === null || value === false || Number.isNaN(Number(value))) {
            return "";
        }
        return String(Number(value));
    }

    startSummaryEdit() {
        this.state.summaryMessage = "";
        this.state.summaryErrors = {};
        this.resetSummaryForm();
        this.state.summaryEditMode = true;
    }

    cancelSummaryEdit() {
        this.state.summaryErrors = {};
        this.resetSummaryForm();
        this.state.summaryEditMode = false;
    }

    onSummaryFieldInput(fieldName, event) {
        const value = event.target.value;
        this.state.summaryMessage = "";
        this.state.summaryForm[fieldName] = value;
        if (fieldName === "annualDepreciation" || fieldName === "monthlyDepreciation" || fieldName === "depreciableAmount") {
            this.state.summaryDriverField = fieldName;
        }
        if (fieldName === "depreciationMethod" || fieldName === "usefulLifeYears" || fieldName === "residualValue" || fieldName === "annualDepreciation" || fieldName === "monthlyDepreciation" || fieldName === "depreciableAmount") {
            this.syncSummaryDerivedValues(fieldName);
        }
        this.state.summaryErrors = this.validateSummaryForm();
    }

    syncSummaryDerivedValues(changedField) {
        const usefulLife = Number(this.state.summaryForm.usefulLifeYears);
        if (!Number.isFinite(usefulLife) || usefulLife <= 0) {
            return;
        }
        const method = this.state.summaryForm.depreciationMethod || "straight_line";
        const months = method === "purchase_date" ? 1 : usefulLife * 12;
        if (!months) {
            return;
        }
        if (method === "straight_line" || method === "purchase_date") {
            const summaryInputs = this.state.data.summaryInputs || {};
            const purchasePrice = Number(summaryInputs.purchasePrice || 0);
            const residualValue = Number(this.state.summaryForm.residualValue || 0);
            if (!Number.isFinite(purchasePrice) || !Number.isFinite(residualValue)) {
                return;
            }
            const depreciable = Math.max(purchasePrice - residualValue, 0);
            const monthly = depreciable / months;
            this.state.summaryForm.depreciableAmount = this.decimalToInput(depreciable);
            this.state.summaryForm.monthlyDepreciation = this.decimalToInput(monthly);
            this.state.summaryForm.annualDepreciation = this.decimalToInput(method === "purchase_date" ? depreciable : depreciable / usefulLife);
            this.state.summaryDriverField = "depreciableAmount";
            return;
        }
        if (changedField === "monthlyDepreciation") {
            const monthly = Number(this.state.summaryForm.monthlyDepreciation);
            if (!Number.isFinite(monthly)) {
                return;
            }
            this.state.summaryForm.annualDepreciation = this.decimalToInput(monthly * 12);
            this.state.summaryForm.depreciableAmount = this.decimalToInput(monthly * months);
            return;
        }
        if (changedField === "annualDepreciation") {
            const annual = Number(this.state.summaryForm.annualDepreciation);
            if (!Number.isFinite(annual)) {
                return;
            }
            const monthly = annual / 12;
            this.state.summaryForm.monthlyDepreciation = this.decimalToInput(monthly);
            this.state.summaryForm.depreciableAmount = this.decimalToInput(monthly * months);
            return;
        }
        const depreciable = Number(this.state.summaryForm.depreciableAmount);
        if (!Number.isFinite(depreciable)) {
            return;
        }
        const monthly = depreciable / months;
        this.state.summaryForm.monthlyDepreciation = this.decimalToInput(monthly);
        this.state.summaryForm.annualDepreciation = this.decimalToInput(monthly * 12);
    }

    validateSummaryForm() {
        const errors = {};
        const summaryInputs = this.state.data.summaryInputs || {};
        const purchasePrice = Number(summaryInputs.purchasePrice || 0);
        const usefulLife = Number(this.state.summaryForm.usefulLifeYears);
        const residualValue = Number(this.state.summaryForm.residualValue);
        const annualDepreciation = Number(this.state.summaryForm.annualDepreciation);
        const monthlyDepreciation = Number(this.state.summaryForm.monthlyDepreciation);
        const depreciableAmount = Number(this.state.summaryForm.depreciableAmount);

        if (!Number.isInteger(usefulLife) || usefulLife <= 0) {
            errors.usefulLifeYears = "Useful Life must be greater than 0.";
        }
        if (!this.state.summaryForm.depreciationStartDate) {
            errors.depreciationStartDate = "Depreciation Start Date is required.";
        }
        if (!Number.isFinite(residualValue) || residualValue < 0) {
            errors.residualValue = "Residual Value is required.";
        } else if (residualValue > purchasePrice) {
            errors.residualValue = "Residual Value cannot be greater than Purchase Price.";
        }
        if (!Number.isFinite(annualDepreciation) || annualDepreciation < 0) {
            errors.annualDepreciation = "A valid numeric value is required.";
        }
        if (!Number.isFinite(monthlyDepreciation) || monthlyDepreciation < 0) {
            errors.monthlyDepreciation = "A valid numeric value is required.";
        }
        if (!Number.isFinite(depreciableAmount) || depreciableAmount < 0) {
            errors.depreciableAmount = "A valid numeric value is required.";
        }
        if (!errors.residualValue && Number.isFinite(depreciableAmount) && depreciableAmount > (purchasePrice - residualValue)) {
            errors.depreciableAmount = "Depreciable Amount cannot exceed Purchase Price minus Residual Value.";
        }
        return errors;
    }

    async saveSummaryChanges() {
        this.state.summaryErrors = this.validateSummaryForm();
        if (Object.keys(this.state.summaryErrors).length) {
            return;
        }
        const payload = {
            ...this.state.summaryForm,
            usefulLifeYears: Number(this.state.summaryForm.usefulLifeYears),
            residualValue: Number(this.state.summaryForm.residualValue),
            annualDepreciation: Number(this.state.summaryForm.annualDepreciation),
            monthlyDepreciation: Number(this.state.summaryForm.monthlyDepreciation),
            depreciableAmount: Number(this.state.summaryForm.depreciableAmount),
            driverField: this.state.summaryDriverField,
        };
        const result = await this.orm.call("kio.asset.dashboard.service", "update_depreciation_summary", [this.state.selectedAssetId, payload]);
        if (result && result.success) {
            this.applyDashboardResult(result, "Depreciation Summary updated successfully.");
            return;
        }
        this.state.summaryMessage = (result && result.message) || "";
        this.state.summaryErrors = (result && result.errors) || {};
    }

    backToAssetDashboard() {
        return this.actionService.doAction({
            type: "ir.actions.client",
            tag: "kio_asset_management.asset_dashboard",
            target: "current",
            context: {
                page: "asset_list",
            },
        });
    }

    async runDepreciation() {
        if (!this.state.selectedAssetId) {
            this.notification.add("Please select an asset first.", { type: "danger" });
            return;
        }

        const result = await this.orm.call(
            "kio.asset.dashboard.service",
            "run_asset_depreciation",
            [this.state.selectedAssetId]
        );

        this.applyDashboardResult(result);

        if (result && !result.success) {
            this.notification.add(result.message, {
                type: "danger",
                title: "Validation Error"
            });
        } else if (result && result.success) {
            this.notification.add("Depreciation journal entries processed successfully.", { type: "success" });
        }
    }

    async createJournalEntries() {
        if (!this.state.selectedAssetId) {
            this.notification.add("Please select an asset first.", { type: "danger" });
            return;
        }

        const result = await this.orm.call(
            "kio.asset.dashboard.service",
            "create_depreciation_journal_entries", 
            [this.state.selectedAssetId]
        );

        this.applyDashboardResult(result);

        if (result && !result.success) {
            this.notification.add(result.message, {
                type: "danger",
                title: "Validation Error"
            });
        } else if (result && result.success) {
            this.notification.add("Journal entries created successfully.", { type: "success" });
        }
    }

    moreActions() {
        console.info("More depreciation actions", this.state.selectedAssetId);
    }

    previewJournalEntry() {
        console.info("Preview journal entry", this.state.selectedAssetId);
    }

    openJournalEntry(moveId) {
        if (!moveId) {
            return;
        }
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Journal Entry",
            res_model: "account.move",
            res_id: moveId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    viewScheduleLine(row) {
        if (row && row.journalEntryId) {
            return this.openJournalEntry(row.journalEntryId);
        }
        console.info("View depreciation line", row);
    }
}

registry.category("actions").add("kio_asset_management.depreciation_dashboard", DepreciationDashboard);
