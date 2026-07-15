/** @odoo-module **/
/* global Chart */

import { loadJS } from "@web/core/assets";
import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
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
const ASSET_STATUS_COLORS = {
    Active: "#13a344",
    Assigned: "#2082ff",
    "Under Maintenance": "#ff7a13",
    Unassigned: "#7039bf",
    Retired: "#ee2f43",
    Scrapped: "#8aa0bf",
};
const ASSET_DATE_FIELDS = new Set(["purchaseDate", "warrantyExpiry", "assignDate", "expectedReturnDate", "depreciationStartDate"]);
const ASSET_TEXT_FIELDS = new Set([
    "assetCode",
    "assetName",
    "category",
    "brandModel",
    "serialNumber",
    "barcode",
    "status",
    "assetType",
    "purchasePrice",
    "warrantyExpiry",
    "condition",
    "description",
    "location",
    "buildingFloor",
    "roomArea",
    "department",
    "assignDate",
    "expectedReturnDate",
    "depreciationMethod",
    "usefulLife",
    "residualValue",
    "depreciationStartDate",
    "supplier",
    "invoiceNumber",
    "poNumber",
    "tagsNotes",
]);

export class AssetDashboard extends Component {
    static template = "kio_asset_management.AssetDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.router = useService("router");
        this.assetStatusChartRef = useRef("assetStatusChart");
        this.assetStatusChart = null;
        this.chartJsLoaded = false;
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
            isSavingAsset: false,
            saveAssetError: "",
            selectedStatusLabel: "Total Assets",
            selectedStatusValue: "0",
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
        this.locationOptions = [];
        this.categoryOptions = [];
        this.supplierOptions = [];
        onWillStart(async () => {
            await this.loadChartJs();
            await this.loadDynamicAssetData();
        });
        onMounted(() => this.renderAssetStatusChart());
        onPatched(() => this.syncAssetStatusChartLifecycle());
        onWillUnmount(() => this.destroyAssetStatusChart());
        useBus(this.env.bus, "ROUTE_CHANGE", () => this.restoreRouteState());
        this.updateRoute({ replace: true });
    }

    async loadChartJs() {
        if (window.Chart) {
            this.chartJsLoaded = true;
            return;
        }
        try {
            await loadJS("/web/static/lib/Chart/Chart.js");
            this.chartJsLoaded = Boolean(window.Chart);
        } catch (error) {
            this.chartJsLoaded = false;
            console.warn("Chart.js could not be loaded for asset status chart", error);
        }
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
        const categoryValue = row.categoryId || row.category_id;
        const supplierValue = row.supplierId || row.supplier_id || row.vendorId || row.vendor_id;
        Object.assign(this.addAssetForm, {
            assetCode: row.code,
            assetName: row.name,
            category: this.many2oneName(categoryValue, row.category),
            categoryId: this.many2oneId(categoryValue),
            brandModel: row.brand,
            serialNumber: row.serial,
            barcode: row.barcode || row.serial,
            status: row.status,
            assetType: row.assetType || "Tangible",
            purchaseDate: this.normalizeDateInput(row.purchaseDate),
            purchasePrice: this.moneyToInput(row.price),
            warrantyExpiry: this.normalizeDateInput(row.warrantyExpiry),
            assignDate: this.normalizeDateInput(row.assignDate),
            expectedReturnDate: this.normalizeDateInput(row.expectedReturnDate),
            depreciationStartDate: this.normalizeDateInput(row.depreciationStartDate),
            condition: row.condition || "",
            description: row.description || "",
            supplier: this.many2oneName(supplierValue, row.supplier || row.vendor || ""),
            supplierId: this.many2oneId(supplierValue),
            invoiceNumber: row.invoiceNumber || "",
            poNumber: row.poNumber || "",
            location: row.location,
            locationId: row.locationId ? String(row.locationId) : "",
            buildingFloor: row.buildingFloor || "",
            roomArea: row.roomArea || "",
            department: row.department || row.locationMeta || "",
            assignTo: row.assignedTo,
            assignToId: row.assignedToId ? String(row.assignedToId) : "",
            employeeId: row.employeeCode || "-",
            depreciationMethod: row.depreciationMethod || "straight_line",
            usefulLife: row.usefulLife ? String(row.usefulLife) : "",
            residualValue: row.residualValue !== undefined && row.residualValue !== null ? String(row.residualValue) : "",
            imagePreviewUrl: row.imageUrl || "",
            imageBinary: false,
            active: row.active !== false,
            imageChanged: false,
        });
    }

    async loadDynamicAssetData(options = {}) {
        try {
            const data = await this.orm.call("kio.asset.dashboard.service", "get_asset_dashboard_data", []);
            if (data) {
                this.employeeOptions = (data.employeeOptions || this.employeeOptions).map((employee) => ({
                    ...employee,
                    idValue: `${employee.id}`,
                }));
                this.locationOptions = (data.locationOptions || this.locationOptions).map((location) => ({
                    ...location,
                    idValue: `${location.id}`,
                }));
                this.categoryOptions = (data.categoryOptions || this.categoryOptions).map((category) => ({
                    ...category,
                    idValue: `${category.id}`,
                    label: category.name,
                }));
                this.supplierOptions = (data.supplierOptions || this.supplierOptions).map((supplier) => ({
                    ...supplier,
                    idValue: `${supplier.id}`,
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
                this.resetAssetStatusCenter();
                this.restoreSelectedAsset();
                if (!options.skipFormRestore) {
                    this.restoreAssetForm();
                }
                this.renderAssetStatusChart();
            }
        } catch (error) {
            console.warn("Asset dashboard dynamic data fallback", error);
        } finally {
            this.state.loaded = true;
        }
    }

    parseCount(value) {
        const number = Number(String(value || "0").replace(/,/g, ""));
        return Number.isFinite(number) ? number : 0;
    }

    get totalAssetCount() {
        const totalKpi = this.kpis.find((kpi) => kpi.title === "Total Assets");
        if (totalKpi) {
            return this.parseCount(totalKpi.value);
        }
        return this.statuses.reduce((sum, status) => sum + this.parseCount(status.value), 0);
    }

    get assetStatusLegendItems() {
        const total = this.totalAssetCount;
        return this.statuses.map((status) => {
            const value = this.parseCount(status.value);
            return {
                ...status,
                value,
                displayValue: this.formatInteger(value),
                percent: status.percent || this.formatPercent(value, total),
                color: ASSET_STATUS_COLORS[status.label] || "#8aa0bf",
            };
        });
    }

    resetAssetStatusCenter() {
        this.state.selectedStatusLabel = "Total Assets";
        this.state.selectedStatusValue = this.formatInteger(this.totalAssetCount);
    }

    formatInteger(value) {
        return new Intl.NumberFormat().format(value || 0);
    }

    formatPercent(value, total) {
        return total ? `${((value / total) * 100).toFixed(2)}%` : "0.00%";
    }

    destroyAssetStatusChart() {
        if (this.assetStatusChart) {
            this.assetStatusChart.destroy();
            this.assetStatusChart = null;
        }
    }

    syncAssetStatusChartLifecycle() {
        if (this.state.page !== "dashboard") {
            this.destroyAssetStatusChart();
            return;
        }
        if (!this.assetStatusChart && this.assetStatusChartRef.el) {
            this.renderAssetStatusChart();
        }
    }

    renderAssetStatusChart() {
        if (!this.chartJsLoaded || !this.assetStatusChartRef.el || this.state.page !== "dashboard") {
            return;
        }
        this.destroyAssetStatusChart();

        const legendItems = this.assetStatusLegendItems;
        const labels = legendItems.map((item) => item.label);
        const values = legendItems.map((item) => item.value);
        const statusTotal = values.reduce((sum, item) => sum + item, 0);
        const hasData = statusTotal > 0;
        const chartData = hasData ? values : [1];
        const chartLabels = hasData ? labels : ["No assets"];
        const chartColors = hasData ? legendItems.map((item) => item.color) : ["#e2e8f0"];
        const component = this;
        const percentageLabelsPlugin = {
            id: "assetStatusPercentageLabels",
            afterDatasetsDraw(chart) {
                if (!hasData) {
                    return;
                }
                const dataset = chart.data.datasets[0];
                const total = dataset.data.reduce((sum, item) => sum + Number(item || 0), 0);
                if (!total) {
                    return;
                }
                const ctx = chart.ctx;
                ctx.save();
                ctx.font = "700 12px Inter, Segoe UI, sans-serif";
                ctx.fillStyle = "#ffffff";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                chart.getDatasetMeta(0).data.forEach((arc, index) => {
                    const value = Number(dataset.data[index] || 0);
                    if (!value) {
                        return;
                    }
                    const percentage = (value / total) * 100;
                    const label = percentage >= 3 ? `${percentage.toFixed(1)}%` : "";
                    if (!label) {
                        return;
                    }
                    const position = arc.tooltipPosition();
                    ctx.fillText(label, position.x, position.y);
                });
                ctx.restore();
            },
        };

        const canvas = this.assetStatusChartRef.el;
        canvas.onmouseleave = () => this.resetAssetStatusCenter();
        this.assetStatusChart = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: chartLabels,
                datasets: [{
                    data: chartData,
                    backgroundColor: chartColors,
                    borderColor: "#ffffff",
                    borderWidth: 3,
                    hoverOffset: hasData ? 8 : 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                interaction: {
                    mode: "nearest",
                    intersect: true,
                },
                onHover(event, activeElements) {
                    if (!hasData || !activeElements.length) {
                        component.resetAssetStatusCenter();
                        return;
                    }
                    const index = activeElements[0].index;
                    const item = legendItems[index];
                    component.state.selectedStatusLabel = item.label;
                    component.state.selectedStatusValue = item.displayValue;
                },
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        enabled: hasData,
                        callbacks: {
                            title(items) {
                                const item = items && items[0];
                                return item ? item.label : "";
                            },
                            label(context) {
                                const value = Number(context.raw || 0);
                                const total = context.dataset.data.reduce((sum, item) => sum + Number(item || 0), 0);
                                const percentage = total ? ((value / total) * 100).toFixed(2) : "0.00";
                                const unit = value === 1 ? "asset" : "assets";
                                return `${component.formatInteger(value)} ${unit} (${percentage}%)`;
                            },
                        },
                    },
                },
            },
            plugins: [percentageLabelsPlugin],
        });
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

    get assetPaginationItems() {
        const totalPages = this.assetPageCount;
        const currentPage = Math.min(Math.max(this.state.assetPage, 1), totalPages);
        const visiblePages = new Set([1, totalPages]);

        for (let page = currentPage - 1; page <= currentPage + 1; page += 1) {
            if (page >= 1 && page <= totalPages) {
                visiblePages.add(page);
            }
        }

        const pages = [...visiblePages].sort((left, right) => left - right);
        const items = [];
        let previousPage = 0;

        for (const page of pages) {
            if (page - previousPage > 1) {
                items.push({ key: `ellipsis-${previousPage}-${page}`, type: "ellipsis" });
            }
            items.push({ key: `page-${page}`, type: "page", page });
            previousPage = page;
        }

        return items;
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

    get locationAxisLabels() {
        const max = this.maxLocationValue;
        return [max, max * 0.75, max * 0.5, max * 0.25, 0].map((value) => Math.round(value));
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
        this.resetAddAssetForm();
        this.state.saveAssetError = "";
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
        this.state.saveAssetError = "";
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
        if (this.state.isSavingAsset) {
            return;
        }
        this.state.saveAssetError = "";

        if (this.state.assetFormMode === "edit" && this.state.editingAssetId) {
            this.state.isSavingAsset = true;
            try {
                const assetId = Number(this.state.editingAssetId);
                const vals = this.buildAssetWriteValues();
                await this.orm.write("kio.asset.unit", [assetId], vals);
                await this.loadDynamicAssetData({ skipFormRestore: true });
                const updatedRow = this.assetRows.find((asset) => asset.id === assetId);
                if (updatedRow) {
                    this.selectedAsset = buildAssetDetails(updatedRow);
                    this.fillAssetFormFromRow(updatedRow);
                    this.state.selectedAssetId = assetId;
                }
                this.addAssetForm.imageBinary = false;
                this.addAssetForm.imageChanged = false;
                this.state.imageVersion += 1;
                this.closeAddAsset();
            } catch (error) {
                console.error("Could not save asset", error);
                this.state.saveAssetError = this.errorMessage(error);
            } finally {
                this.state.isSavingAsset = false;
            }
            return;
        }

        // Existing Add Asset flow is intentionally unchanged by the edit-save fix.
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

    onAssetSupplierChange(event) {
        const supplierId = event.target.value || "";
        const supplier = this.supplierOptions.find((item) => item.idValue === supplierId);
        this.addAssetForm.supplierId = supplierId;
        this.addAssetForm.supplier = supplier ? supplier.name : this.addAssetForm.supplier;
    }

    onAssetCategoryChange(event) {
        const categoryId = event.target.value || "";
        const category = this.categoryOptions.find((item) => item.idValue === categoryId);
        this.addAssetForm.categoryId = categoryId;
        this.addAssetForm.category = category ? category.name : this.addAssetForm.category;
    }

    onAssetFormInput(fieldName, event) {
        if (!ASSET_TEXT_FIELDS.has(fieldName)) {
            return;
        }
        this.addAssetForm[fieldName] = event.target.value || "";
    }

    onAssetActiveChange(event) {
        this.addAssetForm.active = Boolean(event.target.checked);
    }

    onAssetLocationChange(event) {
        const locationId = event.target.value || "";
        const location = this.locationOptions.find((item) => item.idValue === locationId);
        this.addAssetForm.locationId = locationId;
        this.addAssetForm.location = location ? location.name : "";
    }

    onAssetDateInput(fieldName, event) {
        if (!ASSET_DATE_FIELDS.has(fieldName)) {
            return;
        }
        this.addAssetForm[fieldName] = event.target.value || "";
    }

    openAssetDatePicker(event) {
        const target = event.currentTarget;
        const wrapper = target.closest ? target.closest(".kio_input_icon") : null;
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

    buildAssetWriteValues() {
        const vals = {
            asset_name: this.optionalText(this.addAssetForm.assetName),
            category_id: this.addAssetForm.categoryId ? Number(this.addAssetForm.categoryId) : false,
            category_name: this.optionalText(this.addAssetForm.category),
            brand_model: this.optionalText(this.addAssetForm.brandModel),
            serial_number: this.optionalText(this.addAssetForm.serialNumber),
            barcode: this.optionalText(this.addAssetForm.barcode),
            status: this.optionalText(this.addAssetForm.status),
            asset_type: this.optionalText(this.addAssetForm.assetType),
            purchase_date: this.normalizeDateInput(this.addAssetForm.purchaseDate) || false,
            purchase_price: this.parseNumberInput(this.addAssetForm.purchasePrice),
            warranty_expiry_date: this.normalizeDateInput(this.addAssetForm.warrantyExpiry) || false,
            condition: this.optionalText(this.addAssetForm.condition),
            description: this.optionalText(this.addAssetForm.description),
            location_id: this.addAssetForm.locationId ? Number(this.addAssetForm.locationId) : false,
            location: this.optionalText(this.addAssetForm.location),
            building_floor: this.optionalText(this.addAssetForm.buildingFloor),
            room_area: this.optionalText(this.addAssetForm.roomArea),
            department_name: this.optionalText(this.addAssetForm.department),
            assigned_employee_id: this.addAssetForm.assignToId ? Number(this.addAssetForm.assignToId) : false,
            assign_date: this.normalizeDateInput(this.addAssetForm.assignDate) || false,
            expected_return_date: this.normalizeDateInput(this.addAssetForm.expectedReturnDate) || false,
            depreciation_method: this.addAssetForm.depreciationMethod || "straight_line",
            useful_life_years: this.parseIntegerInput(this.addAssetForm.usefulLife) || 1,
            residual_value: this.parseNumberInput(this.addAssetForm.residualValue),
            depreciation_start_date: this.normalizeDateInput(this.addAssetForm.depreciationStartDate) || false,
            supplier_id: this.addAssetForm.supplierId ? Number(this.addAssetForm.supplierId) : false,
            supplier: this.optionalText(this.addAssetForm.supplier),
            invoice_number: this.optionalText(this.addAssetForm.invoiceNumber),
            po_number: this.optionalText(this.addAssetForm.poNumber),
            tags_notes: this.optionalText(this.addAssetForm.tagsNotes),
            active: Boolean(this.addAssetForm.active),
        };
        if (this.addAssetForm.imageChanged && this.addAssetForm.imageBinary) {
            vals.image_1920 = this.addAssetForm.imageBinary;
        }
        return vals;
    }

    many2oneId(value) {
        if (Array.isArray(value)) {
            return value[0] ? String(value[0]) : "";
        }
        return value ? String(value) : "";
    }

    many2oneName(value, fallback = "") {
        if (Array.isArray(value)) {
            return value[1] || fallback || "";
        }
        return fallback || "";
    }

    optionalText(value) {
        const text = String(value || "").trim();
        return text && text !== "-" ? text : false;
    }

    parseNumberInput(value) {
        const normalized = String(value || "").replace(/[^0-9.-]/g, "");
        const number = Number(normalized);
        return Number.isFinite(number) ? number : 0;
    }

    parseIntegerInput(value) {
        const number = parseInt(String(value || "").replace(/[^0-9-]/g, ""), 10);
        return Number.isFinite(number) ? number : 0;
    }

    moneyToInput(value) {
        const number = this.parseNumberInput(value);
        return number ? String(number) : "";
    }

    errorMessage(error) {
        return (error && error.data && error.data.message) || (error && error.message) || "The asset could not be saved. Please review the values and try again.";
    }

    normalizeDateInput(value) {
        if (!value || value === "-") {
            return "";
        }
        return String(value).slice(0, 10);
    }

    resetAddAssetForm() {
        Object.assign(this.addAssetForm, {
            assetCode: "",
            assetName: "",
            category: "",
            categoryId: "",
            brandModel: "",
            serialNumber: "",
            barcode: "",
            status: "",
            assetType: "",
            purchaseDate: "",
            purchasePrice: "",
            warrantyExpiry: "",
            condition: "",
            description: "",
            location: "",
            locationId: "",
            buildingFloor: "",
            roomArea: "",
            department: "",
            assignTo: "",
            assignToId: "",
            employeeId: "",
            assignDate: "",
            expectedReturnDate: "",
            depreciationMethod: "",
            usefulLife: "",
            residualValue: "",
            depreciationStartDate: "",
            supplier: "",
            supplierId: "",
            invoiceNumber: "",
            poNumber: "",
            tagsNotes: "",
            active: true,
            imagePreviewUrl: "",
            imageBinary: false,
            imageChanged: false,
        });
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
            categoryId: this.selectedAsset.categoryId ? String(this.selectedAsset.categoryId) : "",
            brandModel: this.selectedAsset.brand,
            serialNumber: this.selectedAsset.serial,
            barcode: this.selectedAsset.barcode,
            status: this.selectedAsset.status,
            assetType: this.selectedAsset.assetType,
            purchaseDate: this.normalizeDateInput(this.selectedAsset.purchaseDate),
            purchasePrice: this.moneyToInput(this.selectedAsset.purchasePrice),
            warrantyExpiry: this.normalizeDateInput(this.selectedAsset.warrantyExpiry),
            condition: this.selectedAsset.condition,
            description: this.selectedAsset.description,
            location: this.selectedAsset.location.location,
            locationId: this.selectedAsset.location.locationId ? String(this.selectedAsset.location.locationId) : "",
            buildingFloor: this.selectedAsset.location.buildingFloor,
            roomArea: this.selectedAsset.location.roomArea,
            department: this.selectedAsset.location.department,
            assignTo: this.selectedAsset.assignment.assignedTo,
            assignToId: this.selectedAsset.assignment.assignedToId ? String(this.selectedAsset.assignment.assignedToId) : "",
            employeeId: this.selectedAsset.assignment.employeeId,
            assignDate: this.normalizeDateInput(this.selectedAsset.assignment.assignDate),
            expectedReturnDate: this.normalizeDateInput(this.selectedAsset.assignment.expectedReturn),
            depreciationMethod: this.selectedAsset.depreciationMethod || "straight_line",
            usefulLife: this.selectedAsset.usefulLife && this.selectedAsset.usefulLife !== "-" ? String(this.selectedAsset.usefulLife).replace(/[^0-9]/g, "") : "",
            residualValue: this.selectedAsset.residualValue !== undefined && this.selectedAsset.residualValue !== null ? String(this.selectedAsset.residualValue) : "",
            depreciationStartDate: this.normalizeDateInput(this.selectedAsset.depreciationStartDate),
            supplier: this.selectedAsset.supplier,
            supplierId: this.selectedAsset.supplierId ? String(this.selectedAsset.supplierId) : "",
            invoiceNumber: this.selectedAsset.invoiceNumber,
            poNumber: this.selectedAsset.poNumber,
            tagsNotes: this.selectedAsset.tagsNotes,
            imagePreviewUrl: this.selectedAsset.imageUrl || "",
            imageBinary: false,
            active: this.selectedAsset.active !== false,
            imageChanged: false,
        });
        this.state.saveAssetError = "";
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
