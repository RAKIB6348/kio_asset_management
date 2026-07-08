/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { assetListKpis, assetRows } from "./asset_list_data";
import { addAssetFormState } from "./add_asset_data";
import { buildAssetDetails } from "./asset_details_data";

export class AssetDashboard extends Component {
    static template = "kio_asset_management.AssetDashboard";

    setup() {
        this.state = useState({ page: "dashboard", previousPage: "dashboard" });
        this.assetListKpis = assetListKpis;
        this.assetRows = assetRows;
        this.addAssetForm = addAssetFormState;
        this.selectedAsset = buildAssetDetails(assetRows[0]);
        this.kpis = [
            { title: "Total Assets", value: "1,248", meta: "View all assets", icon: "fa-cube", tone: "blue", action: true, page: "asset_list" },
            { title: "Active Assets", value: "1,089", meta: "87.25% of total", icon: "fa-check", tone: "green" },
            { title: "Assigned Assets", value: "842", meta: "67.63% of total", icon: "fa-user", tone: "orange" },
            { title: "Under Maintenance", value: "52", meta: "4.17% of total", icon: "fa-clock-o", tone: "purple" },
            { title: "Unassigned Assets", value: "247", meta: "19.79% of total", icon: "fa-ban", tone: "red" },
            { title: "Depreciated Value", value: "৳ 8.45M", meta: "View depreciation", icon: "fa-money", tone: "teal", action: true },
            { title: "Asset Purchase Value", value: "৳ 24.35M", meta: "View details", icon: "fa-database", tone: "violet", action: true },
            { title: "Current Asset Value", value: "৳ 15.90M", meta: "View details", icon: "fa-line-chart", tone: "lime", action: true },
        ];
        this.actions = [
            { label: "Add Asset", icon: "fa-plus", tone: "blue", page: "add_asset" },
            { label: "Assign Asset", icon: "fa-user-plus", tone: "green" },
            { label: "Maintenance Request", icon: "fa-wrench", tone: "orange" },
            { label: "View Reports", icon: "fa-bar-chart", tone: "purple" },
        ];
        this.statuses = [
            { label: "Active", value: "1,089", percent: "87.25%", tone: "green" },
            { label: "Assigned", value: "842", percent: "67.63%", tone: "blue" },
            { label: "Under Maintenance", value: "52", percent: "4.17%", tone: "orange" },
            { label: "Unassigned", value: "247", percent: "19.79%", tone: "purple" },
            { label: "Retired", value: "16", percent: "1.28%", tone: "red" },
            { label: "Scrapped", value: "2", percent: "0.16%", tone: "slate" },
        ];
        this.locations = [
            { label: "Head Office", value: 420, tone: "blue" },
            { label: "Chattogram Branch", value: 210, tone: "teal" },
            { label: "Sylhet Branch", value: 165, tone: "amber" },
            { label: "Khulna Branch", value: 125, tone: "purple" },
            { label: "Warehouse", value: 85, tone: "red" },
        ];
        this.maintenanceCounts = [
            { label: "New Request", value: 12, tone: "purple" },
            { label: "In Progress", value: 18, tone: "blue" },
            { label: "Waiting Parts", value: 7, tone: "orange" },
            { label: "Completed", value: 45, tone: "green" },
            { label: "Cancelled", value: 3, tone: "red" },
        ];
        this.assignedAssets = [
            { asset: "HP Laptop 840 G5", code: "AST-0001", assignedTo: "John Doe", department: "IT Department", date: "20 May 2024", status: "Active" },
            { asset: "Dell Monitor 24\"", code: "AST-0002", assignedTo: "Jane Smith", department: "Accounts", date: "18 May 2024", status: "Active" },
            { asset: "Canon Printer LBP2900", code: "AST-0003", assignedTo: "Michael Brown", department: "HR Department", date: "17 May 2024", status: "Active" },
            { asset: "iPhone 13", code: "AST-0004", assignedTo: "Emily Davis", department: "Sales Department", date: "15 May 2024", status: "Active" },
            { asset: "Office Chair", code: "AST-0005", assignedTo: "William Wilson", department: "Admin Department", date: "14 May 2024", status: "Active" },
        ];
        this.maintenanceRequests = [
            { request: "MR-00058", date: "20 May 2024", asset: "HP Laptop 840 G5", code: "AST-0001", requestedBy: "John Doe", status: "New", tone: "purple" },
            { request: "MR-00057", date: "19 May 2024", asset: "Dell Monitor 24\"", code: "AST-0002", requestedBy: "Jane Smith", status: "In Progress", tone: "blue" },
            { request: "MR-00056", date: "18 May 2024", asset: "Canon Printer LBP2900", code: "AST-0003", requestedBy: "Michael Brown", status: "Waiting Parts", tone: "orange" },
            { request: "MR-00055", date: "17 May 2024", asset: "Office Chair", code: "AST-0005", requestedBy: "William Wilson", status: "Completed", tone: "green" },
            { request: "MR-00054", date: "16 May 2024", asset: "iPhone 13", code: "AST-0004", requestedBy: "Emily Davis", status: "Completed", tone: "green" },
        ];
        this.depreciationSummary = [
            { label: "Total Assets", value: "1,248", icon: "fa-calculator", tone: "blue" },
            { label: "Total Purchase Value", value: "৳ 24,350,000", icon: "fa-shopping-bag", tone: "slate" },
            { label: "Accumulated Depreciation", value: "৳ 8,450,000", icon: "fa-refresh", tone: "red" },
            { label: "Current Book Value", value: "৳ 15,900,000", icon: "fa-briefcase", tone: "green" },
            { label: "Monthly Depreciation", value: "৳ 320,000", icon: "fa-clock-o", tone: "purple" },
            { label: "Yearly Depreciation", value: "৳ 3,840,000", icon: "fa-calendar", tone: "orange" },
        ];
    }

    handleKpiClick(kpi) {
        if (kpi.page === "asset_list") {
            this.state.page = "asset_list";
        }
    }

    handleQuickAction(action) {
        if (action.page === "add_asset") {
            this.openAddAsset();
        }
    }

    openAddAsset() {
        this.state.previousPage = this.state.page;
        this.state.page = "add_asset";
    }

    openAssetDetails(row) {
        this.selectedAsset = buildAssetDetails(row);
        this.state.previousPage = "asset_list";
        this.state.page = "asset_details";
    }

    backToAssetList() {
        this.state.page = "asset_list";
    }

    closeAddAsset() {
        this.state.page = this.state.previousPage || "dashboard";
    }

    saveAsset() {
        // Placeholder hook for future ORM/RPC persistence.
        console.info("Save Asset", this.addAssetForm);
        this.closeAddAsset();
    }

    editAsset() {
        console.info("Edit Asset", this.selectedAsset);
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
            employeeId: this.selectedAsset.assignment.employeeId,
            assignDate: this.selectedAsset.assignment.assignDate,
            expectedReturnDate: this.selectedAsset.assignment.expectedReturn,
            supplier: this.selectedAsset.supplier,
            invoiceNumber: this.selectedAsset.invoiceNumber,
            poNumber: this.selectedAsset.poNumber,
            tagsNotes: this.selectedAsset.tagsNotes,
        });
        this.openAddAsset();
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

    openDashboard() {
        this.state.page = "dashboard";
    }
}

registry.category("actions").add("kio_asset_management.asset_dashboard", AssetDashboard);
