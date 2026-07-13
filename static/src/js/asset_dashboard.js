/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { assetListKpis, assetRows } from "./asset_list_data";
import { addAssetFormState } from "./add_asset_data";
import { buildAssetDetails } from "./asset_details_data";

const ROUTE_KEYS = {
    page: "kio_asset_page",
    previousPage: "kio_asset_previous_page",
    selectedAssetId: "kio_asset_id",
    assetSearch: "kio_asset_search",
    assetPage: "kio_asset_page_no",
    assetPageSize: "kio_asset_page_size",
    assetFormMode: "kio_asset_form_mode",
    editingAssetId: "kio_asset_editing_id",
};

const VALID_PAGES = new Set(["dashboard", "asset_list", "asset_details", "add_asset"]);
const VALID_FORM_MODES = new Set(["create", "edit"]);

export class AssetDashboard extends Component {
    static template = "kio_asset_management.AssetDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.router = useService("router");
        const context = (this.props.action && this.props.action.context) || {};
        const initialRouteState = this.getRouteState(context);
        this.state = useState({
            page: initialRouteState.page,
            previousPage: initialRouteState.previousPage,
            loaded: false,
            assetSearch: initialRouteState.assetSearch,
            assetPage: initialRouteState.assetPage,
            assetPageSize: initialRouteState.assetPageSize,
            assetFormMode: initialRouteState.assetFormMode,
            editingAssetId: initialRouteState.editingAssetId,
            selectedAssetId: initialRouteState.selectedAssetId,
            imageVersion: 0,
        });
        this.assetListKpis = assetListKpis;
        this.assetRows = assetRows;
        this.addAssetForm = addAssetFormState;
        this.selectedAsset = buildAssetDetails();
        this.kpis = [
            { title: "Total Assets", value: "0", meta: "View all assets", icon: "fa-cube", tone: "blue", action: true, page: "asset_list" },
            { title: "Active Assets", value: "0", meta: "0.00% of total", icon: "fa-check", tone: "green" },
            { title: "Assigned Assets", value: "0", meta: "0.00% of total", icon: "fa-user", tone: "orange" },
            { title: "Under Maintenance", value: "0", meta: "0.00% of total", icon: "fa-clock-o", tone: "purple" },
            { title: "Unassigned Assets", value: "0", meta: "0.00% of total", icon: "fa-ban", tone: "red" },
            { title: "Depreciated Value", value: "0.00", meta: "View depreciation", icon: "fa-money", tone: "teal", action: true },
            { title: "Asset Purchase Value", value: "0.00", meta: "View details", icon: "fa-database", tone: "violet", action: true },
            { title: "Current Asset Value", value: "0.00", meta: "View details", icon: "fa-line-chart", tone: "lime", action: true },
        ];
        this.actions = [
            { label: "Add Asset", icon: "fa-plus", tone: "blue", page: "add_asset" },
            { label: "Assign Asset", icon: "fa-user-plus", tone: "green" },
            { label: "Maintenance Request", icon: "fa-wrench", tone: "orange" },
            { label: "View Reports", icon: "fa-bar-chart", tone: "purple" },
        ];
        this.statuses = [
            { label: "Active", value: "0", percent: "0.00%", tone: "green" },
            { label: "Assigned", value: "0", percent: "0.00%", tone: "blue" },
            { label: "Under Maintenance", value: "0", percent: "0.00%", tone: "orange" },
            { label: "Unassigned", value: "0", percent: "0.00%", tone: "purple" },
            { label: "Retired", value: "0", percent: "0.00%", tone: "red" },
            { label: "Scrapped", value: "0", percent: "0.00%", tone: "slate" },
        ];
        this.locations = [];
        this.maintenanceCounts = [];
        this.assignedAssets = [];
        this.maintenanceRequests = [];
        this.depreciationSummary = [
            { label: "Total Assets", value: "0", icon: "fa-calculator", tone: "blue" },
            { label: "Total Purchase Value", value: "0.00", icon: "fa-shopping-bag", tone: "slate" },
            { label: "Accumulated Depreciation", value: "0.00", icon: "fa-refresh", tone: "red" },
            { label: "Current Book Value", value: "0.00", icon: "fa-briefcase", tone: "green" },
            { label: "Monthly Depreciation", value: "0.00", icon: "fa-clock-o", tone: "purple" },
            { label: "Yearly Depreciation", value: "0.00", icon: "fa-calendar", tone: "orange" },
        ];
        this.assetDetailsByCode = {};
        this.employeeOptions = [];
        onWillStart(async () => this.loadDynamicAssetData());
        useBus(this.env.bus, "ROUTE_CHANGE", () => this.restoreRouteState());
        this.updateRoute({ replace: true });
    }

    getRouteState(context = {}) {
        const hash = (this.router && this.router.current && this.router.current.hash) || {};
        const page = this.sanitizePage(hash[ROUTE_KEYS.page] || context.page);
        const previousPage = this.sanitizePage(hash[ROUTE_KEYS.previousPage] || context.previous_page || page);
        return {
            page,
            previousPage,
            selectedAssetId: this.parsePositiveNumber(hash[ROUTE_KEYS.selectedAssetId] || context.asset_id),
            assetSearch: hash[ROUTE_KEYS.assetSearch] || "",
            assetPage: this.parsePositiveNumber(hash[ROUTE_KEYS.assetPage]) || 1,
            assetPageSize: this.parsePositiveNumber(hash[ROUTE_KEYS.assetPageSize]) || 10,
            assetFormMode: this.sanitizeFormMode(hash[ROUTE_KEYS.assetFormMode]),
            editingAssetId: this.parsePositiveNumber(hash[ROUTE_KEYS.editingAssetId]) || false,
        };
    }

    sanitizePage(page) {
        return VALID_PAGES.has(page) ? page : "dashboard";
    }

    sanitizeFormMode(mode) {
        return VALID_FORM_MODES.has(mode) ? mode : "create";
    }

    parsePositiveNumber(value) {
        const number = Number(value);
        return Number.isFinite(number) && number > 0 ? number : false;
    }

    routeHashForState() {
        const isDetails = this.state.page === "asset_details";
        const isEdit = this.state.page === "add_asset" && this.state.assetFormMode === "edit";
        return {
            [ROUTE_KEYS.page]: this.state.page === "dashboard" ? undefined : this.state.page,
            [ROUTE_KEYS.previousPage]: this.state.previousPage && this.state.previousPage !== this.state.page ? this.state.previousPage : undefined,
            [ROUTE_KEYS.selectedAssetId]: (isDetails || isEdit) && this.state.selectedAssetId ? this.state.selectedAssetId : undefined,
            [ROUTE_KEYS.assetSearch]: this.state.assetSearch || undefined,
            [ROUTE_KEYS.assetPage]: this.state.assetPage > 1 ? this.state.assetPage : undefined,
            [ROUTE_KEYS.assetPageSize]: this.state.assetPageSize !== 10 ? this.state.assetPageSize : undefined,
            [ROUTE_KEYS.assetFormMode]: this.state.page === "add_asset" ? this.state.assetFormMode : undefined,
            [ROUTE_KEYS.editingAssetId]: isEdit && this.state.editingAssetId ? this.state.editingAssetId : undefined,
        };
    }

    updateRoute(options = {}) {
        this.router.pushState(this.routeHashForState(), { replace: Boolean(options.replace) });
    }

    restoreRouteState() {
        const routeState = this.getRouteState((this.props.action && this.props.action.context) || {});
        this.state.page = routeState.page;
        this.state.previousPage = routeState.previousPage;
        this.state.assetSearch = routeState.assetSearch;
        this.state.assetPage = routeState.assetPage;
        this.state.assetPageSize = routeState.assetPageSize;
        this.state.assetFormMode = routeState.assetFormMode;
        this.state.editingAssetId = routeState.editingAssetId;
        this.state.selectedAssetId = routeState.selectedAssetId;
        this.restoreSelectedAsset();
        this.restoreAssetForm();
    }

    restoreSelectedAsset() {
        if (!this.assetRows.length) {
            return;
        }
        const selectedRow = this.state.selectedAssetId
            ? this.assetRows.find((row) => row.id === this.state.selectedAssetId)
            : this.assetRows[0];
        if (selectedRow) {
            this.selectedAsset = buildAssetDetails(selectedRow);
        }
    }

    restoreAssetForm() {
        if (this.state.page !== "add_asset" || this.state.assetFormMode !== "edit" || !this.state.editingAssetId) {
            return;
        }
        const row = this.assetRows.find((asset) => asset.id === this.state.editingAssetId);
        if (row) {
            this.fillAssetFormFromRow(row);
        }
    }

    fillAssetFormFromRow(row) {
        Object.assign(this.addAssetForm, {
            assetCode: row.code,
            assetName: row.name,
            category: row.category,
            brandModel: row.brand,
            serialNumber: row.serial,
            barcode: row.serial,
            status: row.status,
            assetType: "Tangible",
            purchaseDate: row.purchaseDate,
            purchasePrice: row.price,
            supplier: row.vendor || "",
            invoiceNumber: row.invoiceNumber || "",
            poNumber: row.poNumber || "",
            location: row.location,
            department: row.locationMeta || "",
            assignTo: row.assignedTo,
            assignToId: row.assignedToId ? String(row.assignedToId) : "",
            employeeId: row.employeeCode || "-",
            imagePreviewUrl: row.imageUrl || "",
            imageBinary: false,
            imageChanged: false,
        });
    }

    async loadDynamicAssetData() {
        try {
            const data = await this.orm.call("kio.asset.dashboard.service", "get_asset_dashboard_data", []);
            if (data) {
                this.employeeOptions = (data.employeeOptions || this.employeeOptions).map((employee) => ({
                    ...employee,
                    idValue: `${employee.id}`,
                }));
            }
            if (data) {
                this.kpis = data.kpis || this.kpis;
                this.assetListKpis = data.assetListKpis || this.assetListKpis;
                this.assetRows = data.assetRows || [];
                this.assetDetailsByCode = data.assetDetailsByCode || {};
                this.statuses = data.statuses || this.statuses;
                this.locations = data.locations || [];
                this.maintenanceCounts = data.maintenanceCounts || [];
                this.maintenanceRequests = data.maintenanceRequests || [];
                this.depreciationSummary = data.depreciationSummary || this.depreciationSummary;
                this.assignedAssets = data.assignedAssets || [];
                this.restoreSelectedAsset();
                this.restoreAssetForm();
            }
        } catch (error) {
            console.warn("Asset dashboard dynamic data fallback", error);
        } finally {
            this.state.loaded = true;
        }
    }

    get filteredAssetRows() {
        const term = (this.state.assetSearch || "").trim().toLowerCase();
        if (!term) {
            return this.assetRows;
        }
        const compactTerm = term.replace(/[^a-z0-9]/g, "");
        return this.assetRows.filter((row) => {
            const assetCode = String(row.code || "").toLowerCase();
            const compactAssetCode = assetCode.replace(/[^a-z0-9]/g, "");
            const assetName = String(row.name || row.assetName || row.display_name || row.displayName || "").toLowerCase();
            return assetCode.includes(term) || compactAssetCode.includes(compactTerm) || assetName.includes(term);
        });
    }

    get displayAssetRows() {
        const start = (this.state.assetPage - 1) * this.state.assetPageSize;
        return this.filteredAssetRows.slice(start, start + this.state.assetPageSize);
    }

    get assetPageCount() {
        return Math.max(Math.ceil(this.filteredAssetRows.length / this.state.assetPageSize), 1);
    }

    get assetListShowingText() {
        const total = this.filteredAssetRows.length;
        if (!total) {
            return "Showing 0 assets";
        }
        const start = ((this.state.assetPage - 1) * this.state.assetPageSize) + 1;
        const end = Math.min(start + this.state.assetPageSize - 1, total);
        return `Showing ${start} to ${end} of ${total} assets`;
    }

    get dashboardTotalAssets() {
        return this.kpis.length ? this.kpis[0].value : "0";
    }

    get maxLocationValue() {
        return Math.max(...this.locations.map((location) => Number(location.value) || 0), 1);
    }

    onAssetSearch(event) {
        this.state.assetSearch = event.target.value;
        this.state.assetPage = 1;
        this.updateRoute({ replace: true });
    }

    setAssetPage(page) {
        this.state.assetPage = Math.min(Math.max(page, 1), this.assetPageCount);
        this.updateRoute({ replace: true });
    }

    nextAssetPage() {
        this.setAssetPage(this.state.assetPage + 1);
    }

    previousAssetPage() {
        this.setAssetPage(this.state.assetPage - 1);
    }

    onAssetPageSizeChange(event) {
        this.state.assetPageSize = Number(event.target.value) || 10;
        this.state.assetPage = 1;
        this.updateRoute({ replace: true });
    }

    handleKpiClick(kpi) {
        if (kpi.page === "asset_list") {
            this.state.page = "asset_list";
            this.state.previousPage = "dashboard";
            this.updateRoute();
        }
    }

    handleQuickAction(action) {
        if (action.page === "add_asset") {
            this.openAddAsset();
        }
    }

    openAddAsset() {
        this.state.previousPage = this.state.page;
        this.state.assetFormMode = "create";
        this.state.editingAssetId = false;
        Object.assign(this.addAssetForm, {
            imagePreviewUrl: "",
            imageBinary: false,
            imageChanged: false,
        });
        this.state.page = "add_asset";
        this.updateRoute();
    }

    openEditAsset(assetId) {
        const row = this.assetRows.find((asset) => asset.id === assetId);
        if (!row) {
            console.warn("Cannot edit asset image without a matching asset row", assetId);
            return;
        }
        this.state.previousPage = "asset_list";
        this.state.assetFormMode = "edit";
        this.state.editingAssetId = assetId;
        this.state.selectedAssetId = assetId;
        this.fillAssetFormFromRow(row);
        this.state.page = "add_asset";
        this.updateRoute();
    }

    openAssetDetails(row) {
        this.selectedAsset = buildAssetDetails(row);
        this.state.selectedAssetId = row.id || false;
        this.state.previousPage = "asset_list";
        this.state.page = "asset_details";
        this.updateRoute();
    }

    backToAssetList() {
        this.state.page = "asset_list";
        this.state.previousPage = "dashboard";
        this.state.selectedAssetId = false;
        this.updateRoute();
    }

    closeAddAsset() {
        this.state.page = this.state.previousPage || "dashboard";
        this.state.assetFormMode = "create";
        this.state.editingAssetId = false;
        this.updateRoute();
    }

    async saveAsset() {
        if (this.state.assetFormMode === "edit" && this.state.editingAssetId) {
            await this.orm.call("kio.asset.dashboard.service", "update_asset_assignment", [this.state.editingAssetId, this.addAssetForm.assignToId || false]);
            if (this.addAssetForm.imageChanged && this.addAssetForm.imageBinary) {
                const imageResult = await this.orm.call("kio.asset.dashboard.service", "update_asset_image", [this.state.editingAssetId, this.addAssetForm.imageBinary]);
                if (imageResult && imageResult.imageUrl) {
                    this.addAssetForm.imagePreviewUrl = `${imageResult.imageUrl}&client_refresh=${Date.now()}`;
                }
                this.addAssetForm.imageBinary = false;
                this.addAssetForm.imageChanged = false;
                this.state.imageVersion += 1;
            }
            await this.loadDynamicAssetData();
            this.closeAddAsset();
            return;
        }

        // Placeholder hook for future ORM/RPC persistence.
        console.info("Save Asset", this.addAssetForm);
        this.closeAddAsset();
    }

    onAssignToChange(event) {
        const employeeId = event.target.value || "";
        const employee = this.employeeOptions.find((item) => item.idValue === employeeId);
        this.addAssetForm.assignToId = employeeId;
        this.addAssetForm.assignTo = employee ? employee.name : "";
        this.addAssetForm.employeeId = employee ? (employee.employeeCode || "-") : "-";
    }

    onAssetImageChange(event) {
        const file = event.target.files && event.target.files[0];
        if (!file) {
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const dataUrl = reader.result || "";
            this.addAssetForm.imagePreviewUrl = dataUrl;
            this.addAssetForm.imageBinary = String(dataUrl).split(",")[1] || false;
            this.addAssetForm.imageChanged = true;
            this.state.imageVersion += 1;
            event.target.value = "";
        };
        reader.readAsDataURL(file);
    }

    editAsset() {
        console.info("Edit Asset", this.selectedAsset);
        this.state.assetFormMode = "edit";
        this.state.editingAssetId = this.selectedAsset.id || false;
        this.state.selectedAssetId = this.selectedAsset.id || false;
        Object.assign(this.addAssetForm, {
            assetCode: this.selectedAsset.code,
            assetName: this.selectedAsset.name,
            category: this.selectedAsset.category,
            brandModel: this.selectedAsset.brand,
            serialNumber: this.selectedAsset.serial,
            barcode: this.selectedAsset.barcode,
            status: this.selectedAsset.status,
            assetType: this.selectedAsset.assetType,
            purchaseDate: this.selectedAsset.purchaseDate,
            purchasePrice: this.selectedAsset.purchasePrice.replace("৳ ", ""),
            warrantyExpiry: this.selectedAsset.warrantyExpiry,
            condition: this.selectedAsset.condition,
            description: this.selectedAsset.description,
            location: this.selectedAsset.location.location,
            buildingFloor: this.selectedAsset.location.buildingFloor,
            roomArea: this.selectedAsset.location.roomArea,
            department: this.selectedAsset.location.department,
            assignTo: this.selectedAsset.assignment.assignedTo,
            assignToId: this.selectedAsset.assignment.assignedToId ? String(this.selectedAsset.assignment.assignedToId) : "",
            employeeId: this.selectedAsset.assignment.employeeId,
            assignDate: this.selectedAsset.assignment.assignDate,
            expectedReturnDate: this.selectedAsset.assignment.expectedReturn,
            supplier: this.selectedAsset.supplier,
            invoiceNumber: this.selectedAsset.invoiceNumber,
            poNumber: this.selectedAsset.poNumber,
            tagsNotes: this.selectedAsset.tagsNotes,
            imagePreviewUrl: this.selectedAsset.imageUrl || "",
            imageBinary: false,
            imageChanged: false,
        });
        this.state.previousPage = this.state.page;
        this.state.page = "add_asset";
        this.updateRoute();
    }

    assignAsset() {
        console.info("Assign Asset", this.selectedAsset);
    }

    moreAssetActions() {
        console.info("More Actions", this.selectedAsset);
    }

    transferAsset() {
        console.info("Transfer Asset", this.selectedAsset);
    }

    createMaintenance() {
        console.info("Create Maintenance", this.selectedAsset);
    }

    printAssetLabel() {
        console.info("Print Label", this.selectedAsset);
    }

    openDepreciationBoard(assetId, lockAsset = false) {
        if (!assetId) {
            return;
        }
        return this.actionService.doAction({
            type: "ir.actions.client",
            tag: "kio_asset_management.depreciation_dashboard",
            target: "current",
            context: {
                active_asset_id: assetId,
                asset_id: assetId,
                depreciation_asset_id: assetId,
                lock_asset_selection: Boolean(lockAsset),
            },
        });
    }

    openDashboard() {
        this.state.page = "dashboard";
        this.state.previousPage = "dashboard";
        this.state.selectedAssetId = false;
        this.state.assetFormMode = "create";
        this.state.editingAssetId = false;
        this.updateRoute();
    }
}

registry.category("actions").add("kio_asset_management.asset_dashboard", AssetDashboard);
