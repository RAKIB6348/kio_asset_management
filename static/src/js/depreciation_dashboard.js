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
        this.state = useState({
            loaded: false,
            selectedAssetId: context.active_asset_id || context.asset_id || false,
            data: this.emptyData(),
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
            progress: {},
            scheduleRows: [],
            totals: {},
            automation: {},
            preview: {},
            emptyMessage: "",
        };
    }

    async loadData(assetId = false) {
        const data = await this.orm.call("kio.asset.dashboard.service", "get_depreciation_dashboard_data", [assetId || false]);
        this.state.data = data || this.emptyData();
        this.state.selectedAssetId = this.state.data.selectedAssetId || false;
        this.state.loaded = true;
    }

    onAssetChange(event) {
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

    runDepreciation() {
        console.info("Run depreciation", this.state.selectedAssetId);
    }

    createJournalEntries() {
        console.info("Create journal entries", this.state.selectedAssetId);
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
