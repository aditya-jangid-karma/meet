/**
 * Google Apps Script to process the Keka Assets Download.
 * 
 * Instructions:
 * 1. Open your Google Sheet.
 * 2. Go to Extensions > Apps Script.
 * 3. Delete the default code and paste this entire file in.
 * 4. Paste your raw data from 'desk.xlsx' into a sheet named "RawData".
 * 5. Create a blank sheet named "ProcessedData".
 * 6. Run the `processAssetData` function.
 */

function processAssetData() {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  
  // Define your source and target sheets
  var sourceSheet = spreadsheet.getSheetByName("RawData"); 
  var targetSheet = spreadsheet.getSheetByName("ProcessedData");
  
  if (!sourceSheet || !targetSheet) {
    SpreadsheetApp.getUi().alert("Please make sure you have tabs named 'RawData' and 'ProcessedData' created at the bottom.");
    return;
  }
  
  // Get all data from the RawData sheet
  var data = sourceSheet.getDataRange().getValues();
  if (data.length === 0) {
    SpreadsheetApp.getUi().alert("No data found in RawData sheet.");
    return;
  }
  
  var processedData = [];
  
  // Loop through every row
  for (var i = 2; i < data.length; i++) {
    var row = data[i];
    
    // Arrays are 0-indexed in Apps Script.
    // Col A = index 0
    // Col M = index 12
    // Col N = index 13
    // Col O = index 14
    
    var colA = row[0] !== undefined ? row[0].toString() : "";
    var colM = row.length > 12 ? row[12] : "";
    var colN = row.length > 13 ? row[13] : "";
    var colO = row.length > 14 ? row[14] : "";
    
    // Replace logic for Asset ID in Column A
    if (colA) {
      // Replace prefixes
      colA = colA.replace(/^MS-?/, "M"); // handles MS or MS-
      colA = colA.replace(/^FS-?/, "F"); // handles FS or FS-
      colA = colA.replace(/^WS-?/, "W"); // handles WS or WS-
      
      // If the prefix isn't at the strict start, but anywhere, uncomment these lines instead:
      // colA = colA.replace("MS", "M");
      // colA = colA.replace("FS", "F");
      // colA = colA.replace("WS", "W");
    }
    
    // Store only the specific columns we care about
    processedData.push([colA, colM, colN, colO]);
  }
  
  // Clear the target sheet to avoid old data lingering
  targetSheet.clearContents();
  
  // Write the filtered and modified data into ProcessedData
  // .getRange(row, column, numRows, numColumns)
  targetSheet.getRange(1, 1, processedData.length, 4).setValues(processedData);
  
  SpreadsheetApp.getUi().alert("Data successfully processed! Extracted columns A, M, N, O and modified Asset IDs.");
}
