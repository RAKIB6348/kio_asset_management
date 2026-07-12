/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DepreciationDashboard extends Component {
    static template = "kio_asset_management.DepreciationDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
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
        });
        onWillStart(async () => this.loadData(this.state.selectedAssetId));
    }

    emptyData() {
        return {
            assetOptions: [],
            methodOptions: [],
            fiscalYearOptions: [],
            journalOptions: [],
            filters: {},
            assetInfo: {},
            summary: {},
            summaryInputs: {},
            progress: {},
            scheduleRows: [],
            totals: {},
            automation: {},
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

    onFromDateChange(event) {
        this.state.data.filters.fromDate = event.target.value;
    }

    onToDateChange(event) {
        this.state.data.filters.toDate = event.target.value;
    }

    onAutoCreateChange(event) {
        this.state.data.automation.autoCreate = event.target.checked;
    }

    onCreateJournalChange(event) {
        this.state.data.automation.createJournal = event.target.value;
    }

    onNextRunDateChange(event) {
        this.state.data.automation.nextRunDate = event.target.value;
    }

    onJournalChange(event) {
        this.state.data.automation.journalId = Number(event.target.value) || false;
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
            this.state.summaryEditMode = false;
            this.state.summaryErrors = {};
        }
        this.state.summaryMessage = result.message || fallbackMessage || "";
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
        if (fieldName === "usefulLifeYears" || fieldName === "residualValue" || fieldName === "annualDepreciation" || fieldName === "monthlyDepreciation" || fieldName === "depreciableAmount") {
            this.syncSummaryDerivedValues(fieldName);
        }
        this.state.summaryErrors = this.validateSummaryForm();
    }

    syncSummaryDerivedValues(changedField) {
        const usefulLife = Number(this.state.summaryForm.usefulLifeYears);
        if (!Number.isFinite(usefulLife) || usefulLife <= 0) {
            return;
        }
        const months = usefulLife * 12;
        if (!months) {
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
        const result = await this.orm.call("kio.asset.dashboard.service", "run_asset_depreciation", [this.state.selectedAssetId || false]);
        this.applyDashboardResult(result, "Depreciation journal entry posted successfully.");
    }

    async createJournalEntries() {
        const result = await this.orm.call("kio.asset.dashboard.service", "create_depreciation_journal_entries", [this.state.selectedAssetId || false]);
        this.applyDashboardResult(result, "Draft journal entries created successfully.");
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
