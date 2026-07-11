/** @odoo-module **/

export const assetDetailsByCode = {
    "AST-0001": {
        code: "AST-2024-0001",
        listCode: "AST-0001",
        name: "HP Laptop 840 G5",
        activeState: "Active",
        serial: "5CD8254J2M",
        category: "IT Equipment",
        brand: "HP / 840 G5",
        assetType: "Tangible",
        status: "Available",
        statusTone: "green",
        barcode: "123456789012",
        condition: "New",
        description: "HP EliteBook 840 G5, 8th Gen Intel Core i5, 8GB RAM, 256GB SSD, 14\" FHD Display, Windows 10 Pro.",
        tagsNotes: "Office use laptop for general operations and documentation.",
        supplier: "Tech Solutions Ltd.",
        invoiceNumber: "INV-2024-0158",
        poNumber: "PO-2024-0087",
        purchaseDate: "20 May 2024",
        purchasePrice: "৳ 65,000.00",
        purchasePriceShort: "৳ 65,000.00",
        currentValue: "৳ 45,833.33",
        accumulatedDepreciation: "৳ 19,166.67",
        warrantyExpiry: "20 May 2026",
        expectedReturn: "-",
        usefulLife: "3 Years",
        invoiceFile: "INV-2024-0158.pdf",
        assignment: {
            assignedTo: "John Doe",
            department: "IT Department",
            employeeId: "EMP-1001",
            assignDate: "21 May 2024",
            expectedReturn: "-",
        },
        location: {
            location: "Head Office",
            buildingFloor: "Building A, 3rd Floor",
            roomArea: "Room 305",
            department: "IT Department",
        },
        maintenanceRows: [
            { requestNo: "MR-00023", requestDate: "10 May 2024", issue: "Battery not charging properly", status: "Completed", statusTone: "green", priority: "Medium", priorityTone: "orange", nextMaintenance: "10 Nov 2024" },
            { requestNo: "MR-00045", requestDate: "01 Jun 2024", issue: "Fan noise issue", status: "In Progress", statusTone: "blue", priority: "High", priorityTone: "red", nextMaintenance: "01 Dec 2024" },
        ],
    },
};

export function buildAssetDetails(row) {
    const existing = assetDetailsByCode[row.code];
    if (existing) {
        return { ...existing, id: row.id, imageUrl: row.imageUrl || existing.imageUrl || "" };
    }
    return {
        id: row.id,
        imageUrl: row.imageUrl || "",
        code: row.code,
        listCode: row.code,
        name: row.name,
        activeState: row.status === "Retired" ? "Inactive" : "Active",
        serial: row.serial,
        category: row.category,
        brand: row.brand,
        assetType: "Tangible",
        status: row.status,
        statusTone: row.tone,
        barcode: "123456789012",
        condition: row.status === "Retired" ? "Used" : "New",
        description: `${row.name} assigned asset record with static sample details.`,
        tagsNotes: "Office use asset for general operations and documentation.",
        supplier: "Tech Solutions Ltd.",
        invoiceNumber: "INV-2024-0158",
        poNumber: "PO-2024-0087",
        purchaseDate: row.purchaseDate,
        purchasePrice: row.price,
        purchasePriceShort: row.price,
        currentValue: "৳ 45,833.33",
        accumulatedDepreciation: "৳ 19,166.67",
        warrantyExpiry: "20 May 2026",
        expectedReturn: "-",
        usefulLife: "3 Years",
        invoiceFile: "INV-2024-0158.pdf",
        assignment: {
            assignedTo: row.assignedTo || "-",
            department: row.assignedMeta || "-",
            employeeId: row.assignedTo === "-" ? "-" : "EMP-1001",
            assignDate: "21 May 2024",
            expectedReturn: "-",
        },
        location: {
            location: row.location,
            buildingFloor: "Building A, 3rd Floor",
            roomArea: "Room 305",
            department: row.locationMeta || "-",
        },
        maintenanceRows: [
            { requestNo: "MR-00023", requestDate: "10 May 2024", issue: "Battery not charging properly", status: "Completed", statusTone: "green", priority: "Medium", priorityTone: "orange", nextMaintenance: "10 Nov 2024" },
            { requestNo: "MR-00045", requestDate: "01 Jun 2024", issue: "Fan noise issue", status: "In Progress", statusTone: "blue", priority: "High", priorityTone: "red", nextMaintenance: "01 Dec 2024" },
        ],
    };
}
