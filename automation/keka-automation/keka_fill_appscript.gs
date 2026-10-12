/**
 * ============================================================================
 * KEKA DESK REPORT — DATA FILLING SCRIPT (Google Apps Script)
 * ============================================================================
 * Reads the imported Keka "desk" report, keeps ONLY columns A, M, N, O, fixes
 * the Asset ID prefix in column A, and writes the result to a destination sheet.
 *
 * Asset ID prefix conversion (column A):
 *     MS...  ->  M...
 *     FS...  ->  F...
 *     WS...  ->  W...
 *
 * HOW TO USE
 *   1. Open the desk.xlsx as a Google Sheet (File > Import, or Save as Google
 *      Sheets). Note the tab name that holds the raw Keka data.
 *   2. Extensions > Apps Script, paste this file, Save.
 *   3. Reload the spreadsheet -> a "Keka Tools" menu appears.
 *   4. Set SOURCE_SHEET_NAME / DEST_SHEET_NAME below to match your tabs.
 *   5. Keka Tools > Fill Desk Data.
 * ============================================================================
 */

// ------------------------------- CONFIG -------------------------------------
var SOURCE_SHEET_NAME = 'desk';        // tab holding the raw imported Keka data
var DEST_SHEET_NAME   = 'Output';      // tab to write the cleaned data into
var SOURCE_HAS_HEADER = true;          // true if row 1 of source is a header row

// Which source columns to pull (1-based: A=1, M=13, N=14, O=15)
var SOURCE_COLS = [1, 13, 14, 15];

// Where to write them in the destination.
//   'consecutive' -> writes into A, B, C, D
//   'original'    -> keeps them in A, M, N, O
var DEST_LAYOUT = 'consecutive';

// Set true to clear the destination sheet before writing.
var CLEAR_DEST_FIRST = true;

// Optional header row to write at the top of the destination.
var WRITE_HEADER = true;
var DEST_HEADER  = ['Asset ID', 'Column M', 'Column N', 'Column O'];
// ----------------------------------------------------------------------------


function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Keka Tools')
    .addItem('Fill Desk Data', 'fillDeskData')
    .addToUi();
}

/**
 * Converts the Asset ID prefix: MS->M, FS->F, WS->W (leading two letters).
 */
function convertAssetId(value) {
  if (value === null || value === undefined) return value;
  var s = String(value).trim();
  // Replace only a leading MS / FS / WS (case-insensitive), keep the rest intact.
  return s.replace(/^(MS|FS|WS)/i, function (m) {
    return m.charAt(0).toUpperCase(); // MS->M, FS->F, WS->W
  });
}

function fillDeskData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var src = ss.getSheetByName(SOURCE_SHEET_NAME);
  if (!src) {
    SpreadsheetApp.getUi().alert('Source sheet "' + SOURCE_SHEET_NAME + '" not found.');
    return;
  }

  var lastRow = src.getLastRow();
  var lastCol = src.getLastColumn();
  if (lastRow === 0) {
    SpreadsheetApp.getUi().alert('Source sheet is empty.');
    return;
  }

  // Read the whole source block once.
  var all = src.getRange(1, 1, lastRow, lastCol).getValues();

  var startRow = SOURCE_HAS_HEADER ? 1 : 0; // skip header row if present
  var out = [];

  for (var r = startRow; r < all.length; r++) {
    var row = all[r];

    // Skip fully empty rows.
    var isEmpty = row.every(function (c) { return c === '' || c === null; });
    if (isEmpty) continue;

    var picked = SOURCE_COLS.map(function (col) {
      var v = row[col - 1]; // col is 1-based
      return v === undefined ? '' : v;
    });

    // Column A (first picked value) = Asset ID -> convert prefix.
    picked[0] = convertAssetId(picked[0]);

    out.push(picked);
  }

  // Destination sheet (create if missing).
  var dest = ss.getSheetByName(DEST_SHEET_NAME);
  if (!dest) dest = ss.insertSheet(DEST_SHEET_NAME);
  if (CLEAR_DEST_FIRST) dest.clear();

  var writeRow = 1;

  if (DEST_LAYOUT === 'original') {
    // Keep A, M, N, O positions.
    if (WRITE_HEADER) {
      SOURCE_COLS.forEach(function (col, i) {
        dest.getRange(1, col).setValue(DEST_HEADER[i]);
      });
      writeRow = 2;
    }
    for (var i = 0; i < out.length; i++) {
      SOURCE_COLS.forEach(function (col, j) {
        dest.getRange(writeRow + i, col).setValue(out[i][j]);
      });
    }
  } else {
    // Consecutive: A, B, C, D.
    if (WRITE_HEADER) {
      dest.getRange(1, 1, 1, DEST_HEADER.length).setValues([DEST_HEADER]);
      writeRow = 2;
    }
    if (out.length > 0) {
      dest.getRange(writeRow, 1, out.length, out[0].length).setValues(out);
    }
  }

  SpreadsheetApp.getUi().alert(
    'Done. Wrote ' + out.length + ' rows to "' + DEST_SHEET_NAME + '".'
  );
}
