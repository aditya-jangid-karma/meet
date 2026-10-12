/**
 * Code.gs - Google Apps Script
 * 
 * Instructions:
 * 1. Go to https://script.google.com/ and create a new project.
 * 2. Paste this code into the editor, replacing the default code.
 * 3. Create a Google Sheet, and copy its URL.
 * 4. Paste the Google Sheet URL into the SPREADSHEET_URL variable below.
 * 5. Click "Deploy" -> "New deployment".
 * 6. Select "Web app" as the type.
 * 7. Set "Execute as" to "Me", and "Who has access" to "Anyone".
 * 8. Click Deploy, authorize the permissions, and copy the Web App URL.
 * 9. Paste that URL into the background.js file of your Chrome Extension.
 */

const SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1dLoiGdSDHXrKLLTolpwKXh4s69XG877gU9ijbgwl8UQ/edit";

function doPost(e) {
  try {
    const sheet = SpreadsheetApp.openByUrl(SPREADSHEET_URL).getActiveSheet();
    const data = JSON.parse(e.postData.contents);

    // Rule: Don't store if essential fields are blank (like Vendor or Property)
    // If the data payload is missing the core attributes, reject the save.
    const isMissingData = !data.vendorCode || !data.vendor || !data.propertyCode || !data.property;

    if (!isMissingData) {
      // Append a new row with the extracted data
      sheet.appendRow([
        data.integrationPackage,
        data.propertyCode,
        data.property,
        data.propertyAddress,
        data.vendorCode,
        data.vendor,
        data.vendorType,
        data.vendorAddress,
        new Date() // Timestamp
      ]);
      
      // Optionally format the header row if it's the first row
      if (sheet.getLastRow() === 1) {
        sheet.getRange(1, 1, 1, 9).setValues([[
          "Integration Package", "Property Code", "Property", "Property Address", 
          "Vendor Code", "Vendor", "Vendor Type", "Vendor Address", "Timestamp"
        ]]);
        sheet.getRange(1, 1, 1, 9).setFontWeight("bold");
      }
      
      return ContentService.createTextOutput("Success").setMimeType(ContentService.MimeType.TEXT);
    } else {
      return ContentService.createTextOutput("Ignored: Missing essential data (like Vendor or Property)").setMimeType(ContentService.MimeType.TEXT);
    }
    
  } catch (error) {
    return ContentService.createTextOutput("Error: " + error.toString()).setMimeType(ContentService.MimeType.TEXT);
  }
}

// To handle CORS preflight if needed (though Chrome Extension using text/plain avoids it usually)
function doOptions(e) {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
  };
  return ContentService.createTextOutput("")
    .setMimeType(ContentService.MimeType.TEXT)
    .setHeaders(headers);
}
