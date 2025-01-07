import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QComboBox, 
                             QVBoxLayout, QFormLayout, QWidget, QToolTip, QHBoxLayout, QListWidget,
                             QMessageBox, QDialog, QDialogButtonBox, QListWidgetItem, QStackedWidget,
                             QTextEdit, QFileDialog, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QTextCursor, QTextDocument, QFont, QTextBlockFormat, QTextCharFormat, QPageLayout
from PyQt5.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter
import sqlite3

## stratstats - a simple python-based stratistics tracker for strat-o-matic pen and paper teams. 
## written with love for my Dad. Find online at https://github.com/randomprecision/stratstats.git
## written January 2025

# Safe conversion functions
def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StratStat - Your Dad's Stat Tracker")
        self.setGeometry(100, 100, 700, 500)
        self.setWindowIcon(QIcon('bball.png'))
        self.db_connection = self.connect_to_database()
        self.create_tables()  # Ensure tables are created if they don't exist
        self.update_database_schema()  # Ensure the database schema is updated
        self.currentRecordIndex = -1 # Initialize with -1 to indicate no record selected
        self.initUI()
        self.checkAndPromptTeams()
        self.updateTeams()
        self.last_action = None  # Track the last action for undo functionality
        self.previous_values = None  # Track the previous values before an update
        self.configButton.clicked.connect(self.openConfig)
    def connect_to_database(self):
        try:
            conn = sqlite3.connect("stratstats.db")
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return None

    def create_tables(self):
        cursor = self.db_connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hitters (
                id INTEGER PRIMARY KEY,
                team_id INTEGER,
                first_name TEXT,
                last_name TEXT,
                games INTEGER,
                ab INTEGER,
                aba INTEGER,
                abr INTEGER,
                runs INTEGER,
                hits INTEGER,
                doubles INTEGER,
                triples INTEGER,
                hr INTEGER,
                rbi INTEGER,
                k INTEGER DEFAULT 0,
                bb INTEGER DEFAULT 0,
                gidp INTEGER DEFAULT 0,
                err INTEGER DEFAULT 0,
                sb INTEGER DEFAULT 0,
                cs INTEGER DEFAULT 0,
                UNIQUE (first_name, last_name),
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        """)
        self.db_connection.commit()
    def update_database_schema(self):
        self.ensure_column_exists("hitters", "sb", "INTEGER DEFAULT 0")
        self.ensure_column_exists("hitters", "cs", "INTEGER DEFAULT 0")
        self.ensure_column_exists("hitters", "gidp", "INTEGER DEFAULT 0")
        self.ensure_column_exists("hitters", "err", "INTEGER DEFAULT 0")
        self.ensure_column_exists("pitchers", "wp", "INTEGER DEFAULT 0")
        self.ensure_column_exists("pitchers", "err", "INTEGER DEFAULT 0")

    def ensure_column_exists(self, table, column, column_type):
        cursor = self.db_connection.cursor()
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [info[1] for info in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            self.db_connection.commit()

    def initUI(self):
        mainLayout = QHBoxLayout()

        # Left side layout
        leftLayout = QVBoxLayout()

        # Team Selection
        self.teamSelector = QComboBox()
        self.teamSelector.addItem("Select Team")
        self.updateTeams()
        leftLayout.addWidget(self.teamSelector)

        # Role Selection
        self.roleSelector = QComboBox()
        self.roleSelector.addItem("Select Role")
        self.roleSelector.addItem("Hitter")
        self.roleSelector.addItem("Pitcher")
        self.roleSelector.currentTextChanged.connect(self.updateFields)
        self.roleSelector.setFixedWidth(100)  # Set the fixed width to 100
        leftLayout.addWidget(self.roleSelector)

        # Config Button (Icon)
        configLayout = QHBoxLayout()
        self.configButton = QPushButton()
        self.configButton.setIcon(QIcon('cog_icon.png'))
        self.configButton.setFixedSize(30, 30)  # Make the button a square

        # Print Stats Button
        self.printButton = QPushButton("Print Stats")
        self.printButton.setFixedSize(100, 30)  # Adjust the size of the button
        self.printButton.clicked.connect(self.openPrintStats)

        configLayout.addWidget(self.configButton)
        configLayout.addWidget(self.printButton)
        leftLayout.addLayout(configLayout)

        # Stacked Widget for Hitter and Pitcher Fields
        self.fieldsStack = QStackedWidget()
        self.hitterFields = self.createHitterFields()
        self.pitcherFields = self.createPitcherFields()
        self.fieldsStack.addWidget(self.hitterFields)
        self.fieldsStack.addWidget(self.pitcherFields)
        leftLayout.addWidget(self.fieldsStack)

        # Add/Update Button
        self.saveButton = QPushButton("Add/Update")
        self.saveButton.clicked.connect(self.saveData)
        leftLayout.addWidget(self.saveButton)

        # Success Label
        self.successLabel = QLabel("")
        leftLayout.addWidget(self.successLabel)

        # Undo Last, Reset Player, and Navigation buttons in the same row
        #self.undoButton = QPushButton("Undo Last")
        self.resetButton = QPushButton("Reset Player")
        self.prevButton = QPushButton("<")
        self.nextButton = QPushButton(">")

        # Set the width similar to the "Print Stats" button
        button_width = self.printButton.sizeHint().width()
       # self.undoButton.setFixedWidth(button_width)
        self.resetButton.setFixedWidth(button_width)
        self.prevButton.setFixedWidth(button_width)
        self.nextButton.setFixedWidth(button_width)

        navUndoResetLayout = QHBoxLayout()
        navUndoResetLayout.addWidget(self.prevButton)
        #navUndoResetLayout.addWidget(self.undoButton)
        navUndoResetLayout.addWidget(self.resetButton)
        navUndoResetLayout.addWidget(self.nextButton)

        self.prevButton.setToolTip("Previous Record")
        self.nextButton.setToolTip("Next Record")
        self.prevButton.clicked.connect(self.showPreviousRecord)
        self.nextButton.clicked.connect(self.showNextRecord)

        leftLayout.addLayout(navUndoResetLayout)

        leftContainer = QWidget()
        leftContainer.setLayout(leftLayout)

        # Right side layout
        rightLayout = QVBoxLayout()

        # Current Players Label
        self.currentPlayersLabel = QLabel("Current Players")
        rightLayout.addWidget(self.currentPlayersLabel)

        self.playerList = QListWidget()
        self.playerList.itemClicked.connect(self.loadPlayerData)
        rightLayout.addWidget(self.playerList)
        self.updatePlayerList()

        rightContainer = QWidget()
        rightContainer.setLayout(rightLayout)

        mainLayout.addWidget(leftContainer)
        mainLayout.addWidget(rightContainer)

        container = QWidget()
        container.setLayout(mainLayout)
        self.setCentralWidget(container)

        self.updateFields()

    def hasChanges(self, original_record, current_record):
        for original, current in zip(original_record, current_record):
            if original != current:
                return True
        return False
    
    def showNextRecord(self):
            team_name = self.teamSelector.currentText()

            if team_name == "Select Team":
                return

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM teams WHERE team_name = ?", (team_name,))
            team_id = cursor.fetchone()[0]

            if self.hitterRadio.isChecked():
                cursor.execute("SELECT first_name, last_name, games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err FROM hitters WHERE team_id = ?", (team_id,))
            elif self.pitcherRadio.isChecked():
                cursor.execute("SELECT first_name, last_name, games, st, ip, ipa, wins, losses, saves, hits, er, hr, k, bb, wp, err FROM pitchers WHERE team_id = ?", (team_id,))
                
            records = cursor.fetchall()

            if self.currentRecordIndex + 1 < len(records):
                self.currentRecordIndex += 1
                record = records[self.currentRecordIndex]
                self.loadRecord(record)
            else:
                self.clearFields()

    def loadRecord(self, record):
        first_name, last_name = record[0], record[1]
        if self.hitterRadio.isChecked():
            self.hitterFirstNameInput.setText(first_name)
            self.hitterLastNameInput.setText(last_name)
            self.hitterGamesInput.setText(str(record[2]))
            self.hitterAtBatsInput.setText(str(record[3]))
            self.hitterAtBatsAvailableInput.setText(str(record[4]))
            self.hitterHitsInput.setText(str(record[5]))
            self.hitterRunsInput.setText(str(record[6]))
            self.hitterDoublesInput.setText(str(record[7]))
            self.hitterTriplesInput.setText(str(record[8]))
            self.hitterHomeRunsInput.setText(str(record[9]))
            self.hitterRBIInput.setText(str(record[10]))
            self.hitterStrikeoutsInput.setText(str(record[11]))
            self.hitterWalksInput.setText(str(record[12]))
            self.hitterStolenBasesInput.setText(str(record[13]))
            self.hitterCaughtStealingInput.setText(str(record[14]))
            self.hitterGIDPInput.setText(str(record[15]))
            self.hitterFieldingErrorsInput.setText(str(record[16]))
        elif self.pitcherRadio.isChecked():
            self.pitcherFirstNameInput.setText(first_name)
            self.pitcherLastNameInput.setText(last_name)
            self.pitcherGamesInput.setText(str(record[2]))
            self.pitcherGamesStartedInput.setText(str(record[3]))
            self.pitcherInningsPitchedInput.setText(str(record[4]))
            self.pitcherInningsPitchedAvailableInput.setText(str(record[5]))
            self.pitcherWinsInput.setText(str(record[6]))
            self.pitcherLossesInput.setText(str(record[7]))
            self.pitcherSavesInput.setText(str(record[8]))
            self.pitcherHoldsInput.setText(str(record[9]))
            self.pitcherHitsInput.setText(str(record[10]))
            self.pitcherEarnedRunsInput.setText(str(record[11]))
            self.pitcherHomeRunsInput.setText(str(record[12]))
            self.pitcherStrikeoutsInput.setText(str(record[13]))
            self.pitcherWalksInput.setText(str(record[14]))
            self.pitcherWildPitchesInput.setText(str(record[15]))
            self.pitcherFieldingErrorsInput.setText(str(record[16]))

    def clearFields(self):
        self.hitterFirstNameInput.clear()
        self.hitterLastNameInput.clear()
        self.hitterGamesInput.clear()
        self.hitterAtBatsInput.clear()
        self.hitterAtBatsAvailableInput.clear()
        self.hitterHitsInput.clear()
        self.hitterRunsInput.clear()
        self.hitterDoublesInput.clear()
        self.hitterTriplesInput.clear()
        self.hitterHomeRunsInput.clear()
        self.hitterRBIInput.clear()
        self.hitterStrikeoutsInput.clear()
        self.hitterWalksInput.clear()
        self.hitterStolenBasesInput.clear()
        self.hitterCaughtStealingInput.clear()
        self.hitterGIDPInput.clear()
        self.hitterFieldingErrorsInput.clear()

        self.pitcherFirstNameInput.clear()
        self.pitcherLastNameInput.clear()
        self.pitcherGamesInput.clear()
        self.pitcherGamesStartedInput.clear()
        self.pitcherInningsPitchedInput.clear()
        self.pitcherInningsPitchedAvailableInput.clear()
        self.pitcherWinsInput.clear()
        self.pitcherLossesInput.clear()
        self.pitcherSavesInput.clear()
        self.pitcherHoldsInput.clear()
        self.pitcherHitsInput.clear()
        self.pitcherEarnedRunsInput.clear()
        self.pitcherHomeRunsInput.clear()
        self.pitcherStrikeoutsInput.clear()
        self.pitcherWalksInput.clear()
        self.pitcherWildPitchesInput.clear()
        self.pitcherFieldingErrorsInput.clear()

    def openConfig(self):
        if not hasattr(self, 'configWindow'):
            self.configWindow = ConfigWindow(self)
        self.configWindow.show()
        self.configWindow.raise_()
        self.configWindow.activateWindow()

    def handle_print_preview(self, printer):
        self.printStatsWindow.print_document(printer)
    
    def hitter_entries(self):
        data = {
            "firstName": self.hitterFirstNameInput.text(),
            "lastName": self.hitterLastNameInput.text(),
            "teamId": self.get_team_id(),
            "games": safe_int(self.hitterGamesInput.text()),
            "atBats": safe_int(self.hitterAtBatsInput.text()),
            "abAvailable": safe_int(self.hitterAtBatsAvailableInput.text()),
            "hits": safe_int(self.hitterHitsInput.text()),
            "runs": safe_int(self.hitterRunsInput.text()),
            "doubles": safe_int(self.hitterDoublesInput.text()),
            "triples": safe_int(self.hitterTriplesInput.text()),
            "homeRuns": safe_int(self.hitterHomeRunsInput.text()),
            "rbi": safe_int(self.hitterRBIInput.text()),
            "strikeouts": safe_int(self.hitterStrikeoutsInput.text()),
            "walks": safe_int(self.hitterWalksInput.text()),
            "stolenBases": safe_int(self.hitterStolenBasesInput.text()),
            "caughtStealing": safe_int(self.hitterCaughtStealingInput.text()),
            "doublePlays": safe_int(self.hitterDoublePlaysInput.text()),
            "errors": safe_int(self.hitterFieldingErrorsInput.text())
        }
        return data

    def pitcher_entries(self):
        data = {
            "firstName": self.pitcherFirstNameInput.text(),
            "lastName": self.pitcherLastNameInput.text(),
            "teamId": self.get_team_id(),
            "games": safe_int(self.pitcherGamesInput.text()),
            "gamesStarted": safe_int(self.pitcherGamesStartedInput.text()),
            "inningsPitched": safe_float(self.pitcherInningsPitchedInput.text()),
            "ipAvailable": safe_float(self.pitcherInningsPitchedAvailableInput.text()),
            "wins": safe_int(self.pitcherWinsInput.text()),
            "losses": safe_int(self.pitcherLossesInput.text()),
            "saves": safe_int(self.pitcherSavesInput.text()),
            "holds": safe_int(self.pitcherHoldsInput.text()),
            "earnedRuns": safe_int(self.pitcherEarnedRunsInput.text()),
            "homeRuns": safe_int(self.pitcherHomeRunsInput.text()),
            "strikeouts": safe_int(self.pitcherStrikeoutsInput.text()),
            "walks": safe_int(self.pitcherWalksInput.text()),
            "wildPitches": safe_int(self.pitcherWildPitchesInput.text()),
            "errors": safe_int(self.pitcherFieldingErrorsInput.text())
        }
        return data

    def get_team_id(self):
        team_name = self.teamSelector.currentText()
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT id FROM teams WHERE team_name = ?", (team_name,))
        team_id = cursor.fetchone()[0]
        return team_id

    def updatePlayerList(self):
        self.playerList.clear()
        team_name = self.teamSelector.currentText()

        if team_name == "Select Team":
            return

        cursor = self.db_connection.cursor()
        cursor.execute("SELECT id FROM teams WHERE team_name = ?", (team_name,))
        team_id = cursor.fetchone()[0]

        players = []
        if self.roleSelector.currentText() == "Hitter":
            cursor.execute("SELECT first_name, last_name, ab, aba, hits, bb FROM hitters WHERE team_id = ?", (team_id,))
            players = cursor.fetchall()
        elif self.roleSelector.currentText() == "Pitcher":
            cursor.execute("SELECT first_name, last_name, ip, ipa, er FROM pitchers WHERE team_id = ?", (team_id,))
            players = cursor.fetchall()

        # Sort players by last name
        players = sorted(players, key=lambda x: x[1])

        for player in players:
            if self.roleSelector.currentText() == "Hitter":
                first_name, last_name, ab, aba, hits, bb = player
                abr = aba - (ab + bb)  # Adjust ABR calculation to include walks
                avg = hits / ab if ab > 0 else 0
                avg_str = f"{avg:.3f}".lstrip('0') if ab > 0 else ".000"
                if first_name and last_name:
                    self.playerList.addItem(f"{first_name} {last_name}  ABR: {abr}  AVG: {avg_str}")
            elif self.roleSelector.currentText() == "Pitcher":
                first_name, last_name, ip, ipa, er = player
                ipr = ipa - ip
                era = (er / ip * 9) if ip > 0 else 0
                era_str = f"{era:.2f}".lstrip('0') if ip > 0 else "0.00"
                if first_name and last_name:
                    self.playerList.addItem(f"{first_name} {last_name}  IPR: {ipr:.1f}  ERA: {era_str}")

        # Set the font to Courier with typewriter style hint
        font = QFont("Courier", 10)
        font.setStyleHint(QFont.TypeWriter)
        self.playerList.setFont(font)

    def loadPlayerData(self, item):
        player = item.text().split()
        first_name_initial = player[0][0]
        last_name = player[1]

        team_name = self.teamSelector.currentText()
        role = self.roleSelector.currentText()

        cursor = self.db_connection.cursor()
        cursor.execute("SELECT id FROM teams WHERE team_name = ?", (team_name,))
        team_id = cursor.fetchone()[0]

        if role == "Hitter":
            cursor.execute("SELECT first_name, last_name, aba FROM hitters WHERE team_id = ? AND first_name LIKE ? AND last_name = ?", (team_id, first_name_initial + '%', last_name))
        elif role == "Pitcher":
            cursor.execute("SELECT first_name, last_name, ipa FROM pitchers WHERE team_id = ? AND first_name LIKE ? AND last_name = ?", (team_id, first_name_initial + '%', last_name))

        player_data = cursor.fetchone()
        
        if player_data:
            self.clearFields()  # Clear all fields first
            if role == "Hitter":
                self.hitterFirstNameInput.setText(player_data[0])
                self.hitterLastNameInput.setText(player_data[1])
                self.hitterAtBatsAvailableInput.setText(str(player_data[2]))
            elif role == "Pitcher":
                self.pitcherFirstNameInput.setText(player_data[0])
                self.pitcherLastNameInput.setText(player_data[1])
                self.pitcherInningsPitchedAvailableInput.setText(str(player_data[2]))

    def resetPlayer(self):
        first_name = self.hitterFirstNameInput.text() or self.pitcherFirstNameInput.text()
        last_name = self.hitterLastNameInput.text() or self.pitcherLastNameInput.text()

        if not first_name or not last_name:
            QMessageBox.critical(self, "Error", "No player selected. Please select a player to reset.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Reset",
            f"Are you sure you want to delete all stats for player {first_name} {last_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            self.roleSelector.setCurrentIndex(0)
            self.teamSelector.setCurrentIndex(0)
            self.clearFields()
            QMessageBox.information(self, "Reset", f"Stats for player {first_name} {last_name} have been reset.")

        
    def updateTeams(self):
        self.teamSelector.clear()
        self.teamSelector.addItem("Select Team")
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT team_name FROM teams")
        teams = cursor.fetchall()
        for team in teams:
            self.teamSelector.addItem(team[0])

    def openPrintStats(self):
        team_name = self.teamSelector.currentText()
        cursor = self.db_connection.cursor()

        # Retrieve team_id and handle NoneType
        cursor.execute("SELECT id FROM teams WHERE team_name = ?", (team_name,))
        result = cursor.fetchone()
        if result is None:
            QMessageBox.information(self, "No Team Selected", "No team selected. Operation aborted.")
            return

        team_id = result[0]
        self.printStatsWindow = PrintStatsWindow(self, self.db_connection, team_id)
        self.printStatsWindow.show()

    def updateFields(self):
        role = self.roleSelector.currentText()
        if role == "Hitter":
            self.fieldsStack.setCurrentWidget(self.hitterFields)
        elif role == "Pitcher":
            self.fieldsStack.setCurrentWidget(self.pitcherFields)
        else:
            self.fieldsStack.setCurrentIndex(-1)
        self.updatePlayerList()

    def checkAndPromptTeams(self):
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams")
        team_count = cursor.fetchone()[0]

        if team_count == 0:
            QMessageBox.information(self, "No Teams Found", "No teams found in the database. Please create at least one team to proceed.")
            self.openConfig()
 
    def createHitterFields(self):
        widget = QWidget()
        layout = QFormLayout()

        # Fixed width for input fields
        name_width = 100
        other_width = 50

        self.hitterFirstNameInput = QLineEdit()
        self.hitterFirstNameInput.setFixedWidth(name_width)
        self.hitterLastNameInput = QLineEdit()
        self.hitterLastNameInput.setFixedWidth(name_width)
        self.hitterGamesInput = QLineEdit()
        self.hitterGamesInput.setFixedWidth(other_width)
        self.hitterAtBatsInput = QLineEdit()
        self.hitterAtBatsInput.setFixedWidth(other_width)
        self.hitterAtBatsAvailableInput = QLineEdit()
        self.hitterAtBatsAvailableInput.setFixedWidth(other_width)
        self.hitterHitsInput = QLineEdit()
        self.hitterHitsInput.setFixedWidth(other_width)
        self.hitterRunsInput = QLineEdit()
        self.hitterRunsInput.setFixedWidth(other_width)
        self.hitterDoublesInput = QLineEdit()
        self.hitterDoublesInput.setFixedWidth(other_width)
        self.hitterTriplesInput = QLineEdit()
        self.hitterTriplesInput.setFixedWidth(other_width)
        self.hitterHomeRunsInput = QLineEdit()
        self.hitterHomeRunsInput.setFixedWidth(other_width)
        self.hitterRBIInput = QLineEdit()
        self.hitterRBIInput.setFixedWidth(other_width)
        self.hitterStrikeoutsInput = QLineEdit()
        self.hitterStrikeoutsInput.setFixedWidth(other_width)
        self.hitterWalksInput = QLineEdit()
        self.hitterWalksInput.setFixedWidth(other_width)
        self.hitterStolenBasesInput = QLineEdit()
        self.hitterStolenBasesInput.setFixedWidth(other_width)
        self.hitterCaughtStealingInput = QLineEdit()
        self.hitterCaughtStealingInput.setFixedWidth(other_width)
        self.hitterGIDPInput = QLineEdit()
        self.hitterGIDPInput.setFixedWidth(other_width)
        self.hitterFieldingErrorsInput = QLineEdit()
        self.hitterFieldingErrorsInput.setFixedWidth(other_width)

        layout.addRow("First Name:", self.hitterFirstNameInput)
        layout.addRow("Last Name:", self.hitterLastNameInput)
        layout.addRow("G:", self.hitterGamesInput)
        layout.addRow("AB:", self.hitterAtBatsInput)
        layout.addRow("ABA:", self.hitterAtBatsAvailableInput)
        layout.addRow("H:", self.hitterHitsInput)
        layout.addRow("R:", self.hitterRunsInput)
        layout.addRow("2B:", self.hitterDoublesInput)
        layout.addRow("3B:", self.hitterTriplesInput)
        layout.addRow("HR:", self.hitterHomeRunsInput)
        layout.addRow("RBI:", self.hitterRBIInput)
        layout.addRow("K:", self.hitterStrikeoutsInput)
        layout.addRow("BB:", self.hitterWalksInput)
        layout.addRow("SB:", self.hitterStolenBasesInput)
        layout.addRow("CS:", self.hitterCaughtStealingInput)
        layout.addRow("GIDP:", self.hitterGIDPInput)
        layout.addRow("ERR:", self.hitterFieldingErrorsInput)

        widget.setLayout(layout)
        return widget

    def createPitcherFields(self):
        widget = QWidget()
        layout = QFormLayout()

        # Fixed width for input fields
        name_width = 100
        other_width = 50

        self.pitcherFirstNameInput = QLineEdit()
        self.pitcherFirstNameInput.setFixedWidth(name_width)
        self.pitcherLastNameInput = QLineEdit()
        self.pitcherLastNameInput.setFixedWidth(name_width)
        self.pitcherGamesInput = QLineEdit()
        self.pitcherGamesInput.setFixedWidth(other_width)
        self.pitcherGamesStartedInput = QLineEdit()
        self.pitcherGamesStartedInput.setFixedWidth(other_width)
        self.pitcherInningsPitchedInput = QLineEdit()
        self.pitcherInningsPitchedInput.setFixedWidth(other_width)
        self.pitcherInningsPitchedAvailableInput = QLineEdit()
        self.pitcherInningsPitchedAvailableInput.setFixedWidth(other_width)
        self.pitcherWinsInput = QLineEdit()
        self.pitcherWinsInput.setFixedWidth(other_width)
        self.pitcherLossesInput = QLineEdit()
        self.pitcherLossesInput.setFixedWidth(other_width)
        self.pitcherSavesInput = QLineEdit()
        self.pitcherSavesInput.setFixedWidth(other_width)
        self.pitcherHoldsInput = QLineEdit()
        self.pitcherHoldsInput.setFixedWidth(other_width)
        self.pitcherHitsInput = QLineEdit()  # New hits input field
        self.pitcherHitsInput.setFixedWidth(other_width)
        self.pitcherEarnedRunsInput = QLineEdit()
        self.pitcherEarnedRunsInput.setFixedWidth(other_width)
        self.pitcherHomeRunsInput = QLineEdit()
        self.pitcherHomeRunsInput.setFixedWidth(other_width)
        self.pitcherStrikeoutsInput = QLineEdit()
        self.pitcherStrikeoutsInput.setFixedWidth(other_width)
        self.pitcherWalksInput = QLineEdit()
        self.pitcherWalksInput.setFixedWidth(other_width)
        self.pitcherWildPitchesInput = QLineEdit()
        self.pitcherWildPitchesInput.setFixedWidth(other_width)
        self.pitcherFieldingErrorsInput = QLineEdit()
        self.pitcherFieldingErrorsInput.setFixedWidth(other_width)

        layout.addRow("First Name:", self.pitcherFirstNameInput)
        layout.addRow("Last Name:", self.pitcherLastNameInput)
        layout.addRow("G:", self.pitcherGamesInput)
        layout.addRow("GS:", self.pitcherGamesStartedInput)
        layout.addRow("IP:", self.pitcherInningsPitchedInput)
        layout.addRow("IPA:", self.pitcherInningsPitchedAvailableInput)
        layout.addRow("W:", self.pitcherWinsInput)
        layout.addRow("L:", self.pitcherLossesInput)
        layout.addRow("SV:", self.pitcherSavesInput)
        layout.addRow("HD:", self.pitcherHoldsInput)
        layout.addRow("H:", self.pitcherHitsInput)  # Added hits input field here
        layout.addRow("ER:", self.pitcherEarnedRunsInput)
        layout.addRow("HR:", self.pitcherHomeRunsInput)
        layout.addRow("K:", self.pitcherStrikeoutsInput)
        layout.addRow("BB:", self.pitcherWalksInput)
        layout.addRow("WP:", self.pitcherWildPitchesInput)
        layout.addRow("ERR:", self.pitcherFieldingErrorsInput)

        widget.setLayout(layout)
        return widget

    def saveAndMoveToNextRecord(self):
        self.saveData()
        self.showNextRecord()

    def initUI(self):
        mainLayout = QHBoxLayout()

        # Left side layout
        leftLayout = QVBoxLayout()

        # Team Selection
        self.teamSelector = QComboBox()
        self.teamSelector.addItem("Select Team")
        self.updateTeams()
        self.teamSelector.setMinimumWidth(100)  # Set the minimum width to 100
        self.teamSelector.setMaximumWidth(100)  # Set the maximum width to 100
        leftLayout.addWidget(self.teamSelector)

        
        leftLayout.addWidget(self.teamSelector)

        # Role Selection
        self.roleSelector = QComboBox()
        self.roleSelector.addItem("Select Role")
        self.roleSelector.addItem("Hitter")
        self.roleSelector.addItem("Pitcher")
        self.roleSelector.currentTextChanged.connect(self.updateFields)
        self.roleSelector.setFixedWidth(100)  # Set the fixed width to 100
        leftLayout.addWidget(self.roleSelector)


        # Config Button (Icon)
        configLayout = QHBoxLayout()
        self.configButton = QPushButton()
        self.configButton.setIcon(QIcon('cog_icon.png'))
        self.configButton.setFixedSize(30, 30)  # Make the button a square

        # Print Stats Button
        self.printButton = QPushButton("Print Stats")
        self.printButton.setFixedSize(100, 30)  # Adjust the size of the button
        self.printButton.clicked.connect(self.openPrintStats)

        configLayout.addWidget(self.configButton)
        configLayout.addWidget(self.printButton)
        leftLayout.addLayout(configLayout)

        # Stacked Widget for Hitter and Pitcher Fields
        self.fieldsStack = QStackedWidget()
        self.hitterFields = self.createHitterFields()
        self.pitcherFields = self.createPitcherFields()
        self.fieldsStack.addWidget(self.hitterFields)
        self.fieldsStack.addWidget(self.pitcherFields)
        leftLayout.addWidget(self.fieldsStack)

        # Add/Update Button
        self.saveButton = QPushButton("Add/Update")
        self.saveButton.clicked.connect(self.saveData)
        self.saveButton.setFixedWidth(100)  # Set the fixed width to 100
        leftLayout.addWidget(self.saveButton)

        # Success Label
        self.successLabel = QLabel("")
        leftLayout.addWidget(self.successLabel)

        # Undo Last, Reset Player, and Navigation buttons in the same row
        # feature not impleemented at this time
        #self.undoButton = QPushButton("Undo Last")
        self.resetButton = QPushButton("Reset Player")
        self.prevButton = QPushButton("<")
        self.nextButton = QPushButton(">")

        # Set the width similar to the "Print Stats" button
        button_width = self.printButton.sizeHint().width()
        #self.undoButton.setFixedWidth(button_width)
        self.resetButton.setFixedWidth(button_width)
        self.prevButton.setFixedWidth(button_width)
        self.nextButton.setFixedWidth(button_width)

        navUndoResetLayout = QHBoxLayout()
        navUndoResetLayout.addWidget(self.prevButton)
      #  navUndoResetLayout.addWidget(self.undoButton)
        navUndoResetLayout.addWidget(self.resetButton)
        navUndoResetLayout.addWidget(self.nextButton)

        self.prevButton.setToolTip("Previous Record")
        self.nextButton.setToolTip("Next Record")
        self.prevButton.clicked.connect(self.showPreviousRecord)
        self.nextButton.clicked.connect(self.showNextRecord)

        leftLayout.addLayout(navUndoResetLayout)

        leftContainer = QWidget()
        leftContainer.setLayout(leftLayout)

        # Right side layout
        rightLayout = QVBoxLayout()

        # Current Players Label
        self.currentPlayersLabel = QLabel("Current Players")
        rightLayout.addWidget(self.currentPlayersLabel)

        self.playerList = QListWidget()
        self.playerList.itemClicked.connect(self.loadPlayerData)
        rightLayout.addWidget(self.playerList)
        self.updatePlayerList()

        rightContainer = QWidget()
        rightContainer.setLayout(rightLayout)

        mainLayout.addWidget(leftContainer)
        mainLayout.addWidget(rightContainer)

        container = QWidget()
        container.setLayout(mainLayout)
        self.setCentralWidget(container)

        self.updateFields()

    def saveData(self):
        role = self.roleSelector.currentText()
        team_name = self.teamSelector.currentText()
        cursor = self.db_connection.cursor()

        # Retrieve team_id and handle NoneType
        cursor.execute("SELECT id FROM teams WHERE team_name = ?", (team_name,))
        result = cursor.fetchone()
        if result is None:
            self.successLabel.setText("No team selected. Operation aborted.")
            return

        team_id = result[0]

        if role == "Hitter":
            first_name = self.hitterFirstNameInput.text()
            last_name = self.hitterLastNameInput.text()
            games = safe_int(self.hitterGamesInput.text())
            ab = safe_int(self.hitterAtBatsInput.text())
            aba = safe_int(self.hitterAtBatsAvailableInput.text())
            hits = safe_int(self.hitterHitsInput.text())
            runs = safe_int(self.hitterRunsInput.text())
            doubles = safe_int(self.hitterDoublesInput.text())
            triples = safe_int(self.hitterTriplesInput.text())
            hr = safe_int(self.hitterHomeRunsInput.text())
            rbi = safe_int(self.hitterRBIInput.text())
            k = safe_int(self.hitterStrikeoutsInput.text())
            bb = safe_int(self.hitterWalksInput.text())
            sb = safe_int(self.hitterStolenBasesInput.text())
            cs = safe_int(self.hitterCaughtStealingInput.text())
            gidp = safe_int(self.hitterGIDPInput.text())
            err = safe_int(self.hitterFieldingErrorsInput.text())

            cursor.execute("SELECT games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err FROM hitters WHERE team_id = ? AND first_name = ? AND last_name = ?", (team_id, first_name, last_name))
            original_record = cursor.fetchone()
            current_record = (games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err)

            if original_record:
                for i, (original_value, current_value) in enumerate(zip(original_record, current_record)):
                    if current_value == 0 and original_value != 0:
                        self.successLabel.setText("No update made due to null input values.")
                        return

            if original_record and self.hasChanges(original_record, current_record):
                cursor.execute("""
                    UPDATE hitters SET games = ?, ab = ?, aba = ?, hits = ?, runs = ?, doubles = ?, triples = ?, hr = ?, rbi = ?, k = ?, bb = ?, sb = ?, cs = ?, gidp = ?, err = ?
                    WHERE team_id = ? AND first_name = ? AND last_name = ?
                """, (games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err, team_id, first_name, last_name))
                self.successLabel.setText("Player data updated successfully.")
            elif not original_record:
                cursor.execute("""
                    INSERT INTO hitters (team_id, first_name, last_name, games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (team_id, first_name, last_name, games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err))
                self.successLabel.setText("Player data added successfully.")

        elif role == "Pitcher":
            first_name = self.pitcherFirstNameInput.text()
            last_name = self.pitcherLastNameInput.text()
            games = safe_int(self.pitcherGamesInput.text())
            st = safe_int(self.pitcherGamesStartedInput.text())
            ip = safe_float(self.pitcherInningsPitchedInput.text())
            ipa = safe_float(self.pitcherInningsPitchedAvailableInput.text())
            wins = safe_int(self.pitcherWinsInput.text())
            losses = safe_int(self.pitcherLossesInput.text())
            saves = safe_int(self.pitcherSavesInput.text())
            holds = safe_int(self.pitcherHoldsInput.text())
            hits = safe_int(self.pitcherHitsInput.text())
            er = safe_int(self.pitcherEarnedRunsInput.text())
            hr = safe_int(self.pitcherHomeRunsInput.text())
            k = safe_int(self.pitcherStrikeoutsInput.text())
            bb = safe_int(self.pitcherWalksInput.text())
            wp = safe_int(self.pitcherWildPitchesInput.text())
            err = safe_int(self.pitcherFieldingErrorsInput.text())

            cursor.execute("SELECT games, st, ip, ipa, wins, losses, saves, holds, hits, er, hr, k, bb, wp, err FROM pitchers WHERE team_id = ? AND first_name = ? AND last_name = ?", (team_id, first_name, last_name))
            original_record = cursor.fetchone()
            current_record = (games, st, ip, ipa, wins, losses, saves, holds, hits, er, hr, k, bb, wp, err)

            if original_record:
                for i, (original_value, current_value) in enumerate(zip(original_record, current_record)):
                    if current_value == 0 and original_value != 0:
                        self.successLabel.setText("No update made due to null input values.")
                        return

            if original_record and self.hasChanges(original_record, current_record):
                cursor.execute("""
                    UPDATE pitchers SET games = ?, st = ?, ip = ?, ipa = ?, wins = ?, losses = ?, saves = ?, holds = ?, hits = ?, er = ?, hr = ?, k = ?, bb = ?, wp = ?, err = ?
                    WHERE team_id = ? AND first_name = ? AND last_name = ?
                """, (games, st, ip, ipa, wins, losses, saves, holds, hits, er, hr, k, bb, wp, err, team_id, first_name, last_name))
                self.successLabel.setText("Player data updated successfully.")
            elif not original_record:
                cursor.execute("""
                    INSERT INTO pitchers (team_id, first_name, last_name, games, st, ip, ipa, wins, losses, saves, holds, hits, er, hr, k, bb, wp, err)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (team_id, first_name, last_name, games, st, ip, ipa, wins, losses, saves, holds, hits, er, hr, k, bb, wp, err))
                self.successLabel.setText("Player data added successfully.")

        # Commit the changes to the database
        self.db_connection.commit()

        # Refresh the player list
        self.updatePlayerList()

        # Clear the fields after saving the data
        self.clearFields()


    def saveHitterData(self, data):
        if self.db_connection:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute("SELECT * FROM hitters WHERE first_name = ? AND last_name = ?", (data["firstName"], data["lastName"]))
                existing = cursor.fetchone()
                cursor.execute("""
                    INSERT INTO hitters (first_name, last_name, team_id, games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, gidp, err, sb, cs) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(first_name, last_name) DO UPDATE SET
                        games=games + excluded.games,
                        ab=ab + excluded.ab,
                        aba=excluded.aba,
                        hits=hits + excluded.hits,
                        runs=runs + excluded.runs,
                        doubles=doubles + excluded.doubles,
                        triples=triples + excluded.triples,
                        hr=hr + excluded.hr,
                        rbi=rbi + excluded.rbi,
                        k=k + excluded.k,
                        bb=bb + excluded.bb,
                        gidp=gidp + excluded.gidp,
                        err=err + excluded.err,
                        sb=sb + excluded.sb,
                        cs=cs + excluded.cs
                """, (data["firstName"], data["lastName"], data["teamId"], data["games"], data["atBats"], data["abAvailable"], data["hits"], data["runs"], data["doubles"], data["triples"], data["homeRuns"], data["rbi"], data["strikeouts"], data["walks"], data["doublePlays"], data["errors"], data["stolenBases"], data["caughtStealing"]))
                self.db_connection.commit()
                print(f"Saving hitter data: {data}")
                self.last_action = ('save', 'hitter', data)
                return existing is None
            except sqlite3.Error as e:
                print(f"Error saving hitter data: {e}")

    def savePitcherData(self, data):
        if self.db_connection:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute("SELECT * FROM pitchers WHERE first_name = ? AND last_name = ?", (data["firstName"], data["lastName"]))
                existing = cursor.fetchone()
                cursor.execute("""
                    INSERT INTO pitchers (first_name, last_name, team_id, games, st, ip, ipa, wins, losses, saves, holds, er, hr, k, bb, wp, err) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(first_name, last_name) DO UPDATE SET
                        games=games + excluded.games,
                        st=st + excluded.st,
                        ip=ip + excluded.ip,
                        ipa=excluded.ipa,
                        wins=wins + excluded.wins,
                        losses=losses + excluded.losses,
                        saves=saves + excluded.saves,
                        holds=holds + excluded.holds,
                        er=er + excluded.er,
                        hr=hr + excluded.hr,
                        k=k + excluded.k,
                        bb=bb + excluded.bb,
                        wp=wp + excluded.wp,
                        err=err + excluded.err
                """, (data["firstName"], data["lastName"], data["teamId"], data["games"], data["gamesStarted"], data["inningsPitched"], data["ipAvailable"], data["wins"], data["losses"], data["saves"], data["holds"], data["earnedRuns"], data["homeRuns"], data["strikeouts"], data["walks"], data["wildPitches"], data["errors"]))
                self.db_connection.commit()
                print(f"Saving pitcher data: {data}")
                self.last_action = ('save', 'pitcher', data)
                return existing is None
            except sqlite3.Error as e:
                print(f"Error saving pitcher data: {e}")

    def undoLastAction(self):
        if not self.last_action:
            QMessageBox.information(self, "Undo", "No actions to undo.")
            return

        action, role, data = self.last_action
        if action == 'save':
            try:
                cursor = self.db_connection.cursor()
                if role == 'hitter':
                    self.restore_previous_values("hitters", data)
                elif role == 'pitcher':
                    self.restore_previous_values("pitchers", data)
                self.db_connection.commit()
                self.updatePlayerList()
                QMessageBox.information(self, "Undo", "Last action undone.")
                self.last_action = None
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Error undoing last action: {e}")

    def restore_previous_values(self, table, data):
        if self.previous_values and self.db_connection:
            cursor = self.db_connection.cursor()
            if table == "hitters":
                cursor.execute("""
                    UPDATE hitters SET
                        games = ?,
                        ab = ?,
                        aba = ?,
                        hits = ?,
                        runs = ?,
                        doubles = ?,
                        triples = ?,
                        hr = ?,
                        rbi = ?,
                        k = ?,
                        bb = ?,
                        gidp = ?,
                        err = ?,
                        sb = ?,
                        cs = ?
                    WHERE first_name = ? AND last_name = ? AND team_id = ?
                """, (self.previous_values[3], self.previous_values[4], self.previous_values[5], self.previous_values[6], self.previous_values[7], self.previous_values[8], self.previous_values[9], self.previous_values[10], self.previous_values[11], self.previous_values[12], self.previous_values[13], self.previous_values[14], self.previous_values[15], self.previous_values[16], self.previous_values[17], data["firstName"], data["lastName"], data["teamId"]))
            elif table == "pitchers":
                cursor.execute("""
                    UPDATE pitchers SET
                        games = ?,
                        st = ?,
                        ip = ?,
                        ipa = ?,
                        wins = ?,
                        losses = ?,
                        saves = ?,
                        holds = ?,
                        er = ?,
                        hr = ?,
                        k = ?,
                        bb = ?,
                        wp = ?,
                        err = ?
                    WHERE first_name = ? AND last_name = ? AND team_id = ?
                """, (self.previous_values[3], self.previous_values[4], self.previous_values[5], self.previous_values[6], self.previous_values[7], self.previous_values[8], self.previous_values[9], self.previous_values[10], self.previous_values[11], self.previous_values[12], self.previous_values[13], self.previous_values[14], self.previous_values[15], self.previous_values[16], data["firstName"], data["lastName"], data["teamId"]))
            self.db_connection.commit()
            self.previous_values = None  # Clear previous values after restoration
    def showPreviousRecord(self):
        current_index = self.playerList.currentRow()
        if current_index > 0:
            self.playerList.setCurrentRow(current_index - 1)
            self.loadPlayerData(self.playerList.currentItem())
        else:
            QMessageBox.information(self, "Info", "This is the first record.")

    def showNextRecord(self):
        current_index = self.playerList.currentRow()
        if current_index < self.playerList.count() - 1:
            self.playerList.setCurrentRow(current_index + 1)
            self.loadPlayerData(self.playerList.currentItem())
        else:
            self.clearFields()

class PrintStatsWindow(QDialog):
    def __init__(self, parent=None, db_connection=None, team_id=None):
        super(PrintStatsWindow, self).__init__(parent)
        self.db_connection = db_connection
        self.team_id = team_id
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Print Stats")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        self.statsText = QTextEdit(self)
        font = QFont("Courier", 9)
        font.setStyleHint(QFont.TypeWriter)  # Set the style hint to TypeWriter
        self.statsText.setFont(font)
        layout.addWidget(self.statsText)

        self.statsText.setText(self.generateStats() + "\n" + self.generatePitchersStats())

        buttonLayout = QHBoxLayout()

        self.printButton = QPushButton("Print Preview")
        self.printButton.clicked.connect(self.printPreview)
        buttonLayout.addWidget(self.printButton)

        self.saveToFileButton = QPushButton("Save to File")
        self.saveToFileButton.clicked.connect(self.saveToFile)
        buttonLayout.addWidget(self.saveToFileButton)

        layout.addLayout(buttonLayout)

        self.setLayout(layout)

    def generateStats(self):
        cursor = self.db_connection.cursor()
        team_id = self.team_id

        hitters_header = "Batters\n"
        hitters_header += "Name               G   AB  ABA  ABR    AVG    SLG    H    R    2B   3B   HR   RBI    K     BB    SB    CS   GIDP  ERR\n"
        hitters_header += "-" * 114 + "\n"
        cursor.execute("SELECT first_name, last_name, games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err FROM hitters WHERE team_id = ?", (team_id,))
        hitters = cursor.fetchall()

        hitters = sorted(hitters, key=lambda x: x[1])

        total_hits = total_ab = total_runs = total_doubles = total_triples = total_hr = total_rbi = total_k = total_bb = total_sb = total_cs = total_gidp = total_err = 0

        hitters_stats = ""
        for hitter in hitters:
            first_name, last_name = hitter[0], hitter[1]
            games, ab, aba, hits, runs, doubles, triples, hr, rbi, k, bb, sb, cs, gidp, err = [safe_int(value) for value in hitter[2:]]
            abr = aba - (ab + bb)
            avg = hits / ab if ab > 0 else 0
            slg = (hits + doubles + 2 * triples + 3 * hr) / ab if ab > 0 else 0
            avg_str = f"{avg:.3f}".lstrip('0') if ab > 0 else ".000"
            slg_str = f"{slg:.3f}".lstrip('0') if ab > 0 else ".000"
            if first_name and last_name:
                hitters_stats += f"{first_name[0]}. {last_name:<12}   {games:2}  {ab:3}  {aba:3}  {abr:3}   {avg_str:<6} {slg_str:<6} {hits:4} {runs:4} {doubles:4} {triples:4} {hr:4} {rbi:5} {k:5} {bb:5} {sb:4} {cs:4} {gidp:5} {err:3}\n"

            total_hits += hits
            total_ab += ab
            total_runs += runs
            total_doubles += doubles
            total_triples += triples
            total_hr += hr
            total_rbi += rbi
            total_k += k
            total_bb += bb
            total_sb += sb
            total_cs += cs
            total_gidp += gidp
            total_err += err

        team_avg = total_hits / total_ab if total_ab > 0 else 0
        team_slg = (total_hits + total_doubles + 2 * total_triples + 3 * total_hr) / total_ab if total_ab > 0 else 0
        avg_str = f"{team_avg:.3f}".lstrip('0') if total_ab > 0 else ".000"
        slg_str = f"{team_slg:.3f}".lstrip('0') if total_ab > 0 else ".000"

        summary_header = "\nHitters Totals\n"
        summary_header += "AVG     SLG     H     R     2B    3B    HR    RBI     K      BB     SB   CS    GIDP  ERR\n"
        summary_stats = f"{avg_str:<6} {slg_str:<6} {total_hits:<5} {total_runs:<5} {total_doubles:<5} {total_triples:<5} {total_hr:<5} {total_rbi:<6} {total_k:<7} {total_bb:<7} {total_sb:<6} {total_cs:<5} {total_gidp:<6} {total_err:<5}\n"

        stats = hitters_header + hitters_stats + summary_header + summary_stats

        return stats

    def generatePitchersStats(self):
        cursor = self.db_connection.cursor()
        team_id = self.team_id

        pitchers_header = "Pitchers\n"
        pitchers_header += "Name               G   GS   IP    IPA    IPR    W   L  SV   H   ER    HR   ERA   K     BB     WP     ERR\n"
        pitchers_header += "-" * 111 + "\n"
        cursor.execute("SELECT first_name, last_name, games, st, ip, ipa, wins, losses, saves, hits, er, hr, k, bb, wp, err FROM pitchers WHERE team_id = ?", (team_id,))
        pitchers = cursor.fetchall()

        total_ip = total_er = total_wins = total_losses = total_saves = total_hits = total_hr = total_k = total_bb = total_wp = total_err = 0

        pitchers_stats = ""
        for pitcher in pitchers:
            first_name, last_name = pitcher[0], pitcher[1]
            games, st, ip, ipa, wins, losses, saves, hits, er, hr, k, bb, wp, err = [safe_float(value) if isinstance(value, float) else safe_int(value) for value in pitcher[2:]]
            ipr = ipa - ip
            era = (er / ip * 9) if ip > 0 else 0
            if first_name and last_name:
                pitchers_stats += f"{first_name[0]}. {last_name:<12}   {games:2}  {st:2}  {ip:5.1f}  {ipa:5.1f}  {ipr:5.1f}  {wins:2}  {losses:2}  {saves:2}  {hits:2}  {er:3}  {hr:3}  {era:5.2f}  {k:5} {bb:5}  {wp:5}  {err:5}\n"

            total_ip += ip
            total_er += er
            total_wins += wins
            total_losses += losses
            total_saves += saves
            total_hits += hits
            total_hr += hr
            total_k += k
            total_bb += bb
            total_wp += wp
            total_err += err

        team_era = (total_er / total_ip * 9) if total_ip > 0 else 0
        era_str = f"{team_era:.2f}".lstrip('0') if total_ip > 0 else "0.00"

        summary_header = "\nPitchers Totals\n"
        summary_header += "IP      ER    HR   ERA       K       BB       WP       ERR\n"
        summary_stats = f"{total_ip:<7.1f} {total_er:<5} {total_hr:<5} {era_str:<9} {total_k:<7} {total_bb:<9} {total_wp:<8} {total_err:<7}\n"

        stats = pitchers_header + pitchers_stats + summary_header + summary_stats

        return stats

    def printPreview(self):
        printer = QPrinter()
        printer.setPaperSize(QPrinter.Letter)  # Set paper size to Letter (8.5 x 11 inches)
        printer.setOrientation(QPrinter.Landscape)  # Set orientation to landscape
        printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)  # Set margins as small as possible
        previewDialog = QPrintPreviewDialog(printer, self)
        previewDialog.paintRequested.connect(self.renderPreview)
        previewDialog.exec_()

    def renderPreview(self, printer):
        # Create separate documents for batters and pitchers
        batters_document = QTextDocument()
        cursor_batters = QTextCursor(batters_document)
        text_format = QTextCharFormat()
        text_format.setFont(QFont("Courier", 9))
        cursor_batters.select(QTextCursor.Document)
        cursor_batters.mergeCharFormat(text_format)
        cursor_batters.insertText(self.generateStats())

        pitchers_document = QTextDocument()
        cursor_pitchers = QTextCursor(pitchers_document)
        cursor_pitchers.select(QTextCursor.Document)
        cursor_pitchers.mergeCharFormat(text_format)
        cursor_pitchers.insertText(self.generatePitchersStats())

        # Print batters document
        batters_document.print_(printer)

        # Print pitchers document
        pitchers_document.print_(printer)

    def saveToFile(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Stats", "", "Text Files (*.txt)")
        if filename:
            with open(filename, 'w') as file:
                file.write(self.statsText.toPlainText())

class ConfigWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setGeometry(150, 150, 300, 200)
        self.db_connection = parent.db_connection
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Create Team
        self.newTeamName = QLineEdit()
        self.newTeamName.setPlaceholderText("New Team Name")
        layout.addWidget(self.newTeamName)

        self.createTeamButton = QPushButton("Create Team")
        self.createTeamButton.clicked.connect(self.createTeam)
        layout.addWidget(self.createTeamButton)

        # Delete Team
        self.teamToDeleteSelector = QComboBox()
        layout.addWidget(self.teamToDeleteSelector)

        self.deleteTeamButton = QPushButton("Delete Team")
        self.deleteTeamButton.clicked.connect(self.deleteTeam)
        layout.addWidget(self.deleteTeamButton)

        # Initialize Database
        self.initDbButton = QPushButton("Initialize Database")
        self.initDbButton.clicked.connect(self.initDatabase)
        layout.addWidget(self.initDbButton)

        # Backup Database
        self.backupDbButton = QPushButton("Backup Database")
        self.backupDbButton.clicked.connect(self.backupDatabase)
        layout.addWidget(self.backupDbButton)

        self.setLayout(layout)
        self.updateTeams()

    def createTeam(self):
        team_name = self.newTeamName.text()
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams WHERE team_name = ?", (team_name,))
        count = cursor.fetchone()[0]

        if count > 0:
            QMessageBox.warning(self, "Duplicate Team", "A team with this name already exists. Please choose a different name.")
        else:
            cursor.execute("INSERT INTO teams (team_name) VALUES (?)", (team_name,))
            self.db_connection.commit()
            self.updateTeams()
            QMessageBox.information(self, "Success", "Team has been created successfully.")
            self.newTeamName.clear()

    def updateTeams(self):
        if self.db_connection:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT team_name FROM teams")
            teams = cursor.fetchall()
            self.teamToDeleteSelector.clear()
            for team in teams:
                self.teamToDeleteSelector.addItem(team[0])

    def deleteTeam(self):
        team_name = self.teamToDeleteSelector.currentText()
        if team_name and self.db_connection:
            confirm = QMessageBox.question(self, "Confirm Delete", 
                                           f"Are you sure you want to delete team '{team_name}'? All statistics will be lost.",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm == QMessageBox.Yes:
                cursor = self.db_connection.cursor()
                try:
                    cursor.execute("DELETE FROM teams WHERE team_name = ?", (team_name,))
                    cursor.execute("DELETE FROM hitters WHERE team_id IN (SELECT id FROM teams WHERE team_name = ?)", (team_name,))
                    cursor.execute("DELETE FROM pitchers WHERE team_id IN (SELECT id FROM teams WHERE team_name = ?)", (team_name,))
                    self.db_connection.commit()
                    QMessageBox.information(self, "Success", f"Team '{team_name}' deleted successfully.")
                    self.updateTeams()
                    self.parent().updateTeams()
                except sqlite3.Error as e:
                    QMessageBox.critical(self, "Error", f"Error deleting team: {e}")

    def initDatabase(self):
        confirm = QMessageBox.question(self, "Confirm Initialization", 
                                       "Are you sure you want to delete all data in the database? All team and player statistics will be lost.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes and self.db_connection:
            cursor = self.db_connection.cursor()
            try:
                cursor.execute("DELETE FROM hitters")
                cursor.execute("DELETE FROM pitchers")
                cursor.execute("DELETE FROM teams")
                self.db_connection.commit()
                QMessageBox.information(self, "Success", "Database initialized successfully.")
                self.updateTeams()
                self.parent().updateTeams()
                self.parent().updatePlayerList()
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Error initializing database: {e}")

    def backupDatabase(self):
        from datetime import datetime
        current_date = datetime.now().strftime('%Y%m%d')
        default_filename = f"stratstats_backup_{current_date}.sql"
        
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Database Backup", default_filename, "SQL Files (*.sql);;All Files (*)", options=options)
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    for line in self.db_connection.iterdump():
                        f.write(f"{line}\n")
                QMessageBox.information(self, "Success", f"Database backup saved to {file_path}.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error backing up database: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

