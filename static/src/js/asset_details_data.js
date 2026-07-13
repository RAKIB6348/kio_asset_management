/** @odoo-module **/

export const assetDetailsByCode = {};

export function buildAssetDetails(row = {}) {
    return {
        id: row.id || false,
        imageUrl: row.imageUrl || "",
        code: row.code || "-",
        listCode: row.code || "-",
        name: row.name || "-",
        activeState: row.status === "Retired" ? "Inactive" : "Active",
        serial: row.serial || "-",
        category: row.category || "-",
        brand: row.brand || "-",
        assetType: "Tangible",
        status: row.status || "Available",
        statusTone: row.tone || "green",
        barcode: row.serial || "-",
        condition: row.status === "Retired" ? "Used" : "New",
        description: row.name || "-",
        tagsNotes: "",
        supplier: row.vendor || "-",
        invoiceNumber: row.invoiceNumber || "-",
        poNumber: row.poNumber || "-",
        purchaseDate: row.purchaseDate || "-",
        purchasePrice: row.price || "-",
        purchasePriceShort: row.price || "-",
        currentValue: row.price || "-",
        accumulatedDepreciation: "-",
        warrantyExpiry: "-",
        expectedReturn: "-",
        usefulLife: "-",
        invoiceFile: row.invoiceNumber || "-",
        assignment: {
            assignedTo: row.assignedTo || "-",
            assignedToId: row.assignedToId || false,
            department: row.assignedMeta || "-",
            employeeId: row.employeeCode || "-",
            assignDate: "-",
            expectedReturn: "-",
        },
        location: {
            location: row.location || "-",
            buildingFloor: "-",
            roomArea: "-",
            department: row.locationMeta || "-",
        },
        maintenanceRows: [],
    };
}
