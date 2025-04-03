from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER
import os
import json
from fpdf import FPDF # Import FPDF
from datetime import datetime # Import datetime
import textwrap # Already imported, but good to note


def sort_agent_signals(signals):
    """Sort agent signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


def print_trading_output(result: dict) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.

    Args:
        result (dict): Dictionary containing decisions and analyst signals for multiple tickers
    """
    decisions = result.get("decisions")
    if not decisions:
        print(f"{Fore.RED}No trading decisions available{Style.RESET_ALL}")
        return

    # Print decisions for each ticker
    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Analysis for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")

        # Prepare analyst signals table for this ticker
        table_data = []
        for agent, signals in result.get("analyst_signals", {}).items():
            if ticker not in signals:
                continue
                
            # Skip Risk Management agent in the signals section
            if agent == "risk_management_agent":
                continue

            signal = signals[ticker]
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = signal.get("signal", "").upper()
            confidence = signal.get("confidence", 0)

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)
            
            # Get reasoning if available
            reasoning_str = ""
            if "reasoning" in signal and signal["reasoning"]:
                reasoning = signal["reasoning"]
                
                # Handle different types of reasoning (string, dict, etc.)
                if isinstance(reasoning, str):
                    reasoning_str = reasoning
                elif isinstance(reasoning, dict):
                    # Convert dict to string representation
                    reasoning_str = json.dumps(reasoning, indent=2)
                else:
                    # Convert any other type to string
                    reasoning_str = str(reasoning)
                
                # Wrap long reasoning text to make it more readable
                wrapped_reasoning = ""
                current_line = ""
                # Use a fixed width of 60 characters to match the table column width
                max_line_length = 60
                for word in reasoning_str.split():
                    if len(current_line) + len(word) + 1 > max_line_length:
                        wrapped_reasoning += current_line + "\n"
                        current_line = word
                    else:
                        if current_line:
                            current_line += " " + word
                        else:
                            current_line = word
                if current_line:
                    wrapped_reasoning += current_line
                
                reasoning_str = wrapped_reasoning

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{confidence}%{Style.RESET_ALL}",
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",
                ]
            )

        # Sort the signals according to the predefined order
        table_data = sort_agent_signals(table_data)

        print(f"\n{Fore.WHITE}{Style.BRIGHT}AGENT ANALYSIS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(
            tabulate(
                table_data,
                headers=[f"{Fore.WHITE}Agent", "Signal", "Confidence", "Reasoning"],
                tablefmt="grid",
                colalign=("left", "center", "right", "left"),
            )
        )

        # Print Trading Decision Table
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        # Get reasoning and format it
        reasoning = decision.get("reasoning", "")
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        if reasoning:
            current_line = ""
            # Use a fixed width of 60 characters to match the table column width
            max_line_length = 60
            for word in reasoning.split():
                if len(current_line) + len(word) + 1 > max_line_length:
                    wrapped_reasoning += current_line + "\n"
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            if current_line:
                wrapped_reasoning += current_line

        decision_data = [
            ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
            ["Quantity", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
            [
                "Confidence",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ],
            ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
        ]
        
        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))

    # Print Portfolio Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []
    
    # Extract portfolio manager reasoning (common for all tickers)
    portfolio_manager_reasoning = None
    for ticker, decision in decisions.items():
        if decision.get("reasoning"):
            portfolio_manager_reasoning = decision.get("reasoning")
            break
            
    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)
        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ]
        )

    headers = [f"{Fore.WHITE}Ticker", "Action", "Quantity", "Confidence"]
    
    # Print the portfolio summary table
    print(
        tabulate(
            portfolio_data,
            headers=headers,
            tablefmt="grid",
            colalign=("left", "center", "right", "right"),
        )
    )
    
    # Print Portfolio Manager's reasoning if available
    if portfolio_manager_reasoning:
        # Handle different types of reasoning (string, dict, etc.)
        reasoning_str = ""
        if isinstance(portfolio_manager_reasoning, str):
            reasoning_str = portfolio_manager_reasoning
        elif isinstance(portfolio_manager_reasoning, dict):
            # Convert dict to string representation
            reasoning_str = json.dumps(portfolio_manager_reasoning, indent=2)
        else:
            # Convert any other type to string
            reasoning_str = str(portfolio_manager_reasoning)
            
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        current_line = ""
        # Use a fixed width of 60 characters to match the table column width
        max_line_length = 60
        for word in reasoning_str.split():
            if len(current_line) + len(word) + 1 > max_line_length:
                wrapped_reasoning += current_line + "\n"
                current_line = word
            else:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        if current_line:
            wrapped_reasoning += current_line
            
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Portfolio Strategy:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{wrapped_reasoning}{Style.RESET_ALL}")


def print_backtest_results(table_rows: list) -> None:
    """Print the backtest results in a nicely formatted table"""
    # Clear the screen
    os.system("cls" if os.name == "nt" else "clear")

    # Split rows into ticker rows and summary rows
    ticker_rows = []
    summary_rows = []

    for row in table_rows:
        if isinstance(row[1], str) and "PORTFOLIO SUMMARY" in row[1]:
            summary_rows.append(row)
        else:
            ticker_rows.append(row)

    
    # Display latest portfolio summary
    if summary_rows:
        latest_summary = summary_rows[-1]
        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")

        # Extract values and remove commas before converting to float
        cash_str = latest_summary[7].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        position_str = latest_summary[6].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        total_str = latest_summary[8].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")

        print(f"Cash Balance: {Fore.CYAN}${float(cash_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Position Value: {Fore.YELLOW}${float(position_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Value: {Fore.WHITE}${float(total_str):,.2f}{Style.RESET_ALL}")
        print(f"Return: {latest_summary[9]}")
        
        # Display performance metrics if available
        if latest_summary[10]:  # Sharpe ratio
            print(f"Sharpe Ratio: {latest_summary[10]}")
        if latest_summary[11]:  # Sortino ratio
            print(f"Sortino Ratio: {latest_summary[11]}")
        if latest_summary[12]:  # Max drawdown
            print(f"Max Drawdown: {latest_summary[12]}")

    # Add vertical spacing
    print("\n" * 2)

    # Print the table with just ticker rows
    print(
        tabulate(
            ticker_rows,
            headers=[
                "Date",
                "Ticker",
                "Action",
                "Quantity",
                "Price",
                "Shares",
                "Position Value",
                "Bullish",
                "Bearish",
                "Neutral",
            ],
            tablefmt="grid",
            colalign=(
                "left",  # Date
                "left",  # Ticker
                "center",  # Action
                "right",  # Quantity
                "right",  # Price
                "right",  # Shares
                "right",  # Position Value
                "right",  # Bullish
                "right",  # Bearish
                "right",  # Neutral
            ),
        )
    )

    # Add vertical spacing
    print("\n" * 4)


def format_backtest_row(
    date: str,
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    shares_owned: float,
    position_value: float,
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
    is_summary: bool = False,
    total_value: float = None,
    return_pct: float = None,
    cash_balance: float = None,
    total_position_value: float = None,
    sharpe_ratio: float = None,
    sortino_ratio: float = None,
    max_drawdown: float = None,
) -> list[any]:
    """Format a row for the backtest results table"""
    # Color the action
    action_color = {
        "BUY": Fore.GREEN,
        "COVER": Fore.GREEN,
        "SELL": Fore.RED,
        "SHORT": Fore.RED,
        "HOLD": Fore.WHITE,
    }.get(action.upper(), Fore.WHITE)

    if is_summary:
        return_color = Fore.GREEN if return_pct >= 0 else Fore.RED
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY{Style.RESET_ALL}",
            "",  # Action
            "",  # Quantity
            "",  # Price
            "",  # Shares
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}",  # Total Position Value
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}",  # Cash Balance
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}",  # Total Value
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",  # Return
            f"{Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}" if sharpe_ratio is not None else "",  # Sharpe Ratio
            f"{Fore.YELLOW}{sortino_ratio:.2f}{Style.RESET_ALL}" if sortino_ratio is not None else "",  # Sortino Ratio
            f"{Fore.RED}{abs(max_drawdown):.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # Max Drawdown
        ]
    else:
        return [
            date,
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{action_color}{action.upper()}{Style.RESET_ALL}",
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{shares_owned:,.0f}{Style.RESET_ALL}",
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
            f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
            f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
        ]


# --- PDF Generation Function ---

class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Unicode font (DejaVu) first, then set as fallback
        # Use absolute path to the fonts directory
        font_dir = '/home/unixdude/tradingAI/src/fonts'
        try:
            # Add fonts using explicit absolute paths, WITH uni=True
            self.add_font("DejaVu", "", os.path.join(font_dir, "DejaVuSans.ttf"), uni=True)
            self.add_font("DejaVu", "B", os.path.join(font_dir, "DejaVuSans-Bold.ttf"), uni=True)
            self.add_font("DejaVu", "I", os.path.join(font_dir, "DejaVuSans-Oblique.ttf"), uni=True)
            self.add_font("DejaVu", "BI", os.path.join(font_dir, "DejaVuSans-BoldOblique.ttf"), uni=True)
            # Now set as fallback
            self.set_fallback_fonts(["DejaVu"])
        except Exception as e: # Catch broader exceptions during font loading/setting
             print(f"{Fore.RED}FPDF Error adding/setting font: {e}. Ensure font files are in {font_dir}.{Style.RESET_ALL}")
             # Continue without unicode font if adding fails, might still error later

    def header(self):
        self.set_font('DejaVu', 'B', 11) # Reduced size
        self.cell(0, 8, 'AI Hedge Fund Analysis Report', 0, 1, 'C') # Reduced height
        self.set_font('DejaVu', '', 7) # Reduced size
        self.cell(0, 4, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C') # Reduced height
        self.ln(2) # Reduced spacing

    def footer(self):
        self.set_y(-12) # Move footer up slightly
        self.set_font('DejaVu', 'I', 7) # Reduced size
        self.cell(0, 8, f'Page {self.page_no()}', 0, 0, 'C') # Reduced height

    def chapter_title(self, title):
        self.set_font('DejaVu', 'B', 13) # Reduced size
        self.cell(0, 8, title, 0, 1, 'L') # Reduced height
        self.ln(1) # Reduced spacing

    def section_title(self, title):
        self.set_font('DejaVu', 'B', 11) # Reduced size
        self.cell(0, 6, title, 0, 1, 'L') # Reduced height
        self.ln(1) # Reduced spacing

    def write_table(self, headers, data, col_widths):
        cell_height = 4.5 # Reduced cell height
        header_height = 5 # Reduced header height
        line_height_ratio = 1.0 # Adjust line height within cells if needed

        self.set_font('DejaVu', 'B', 8) # Reduced size
        # Header - Check page break before drawing
        if self.get_y() + header_height > self.page_break_trigger:
            self.add_page()
        for i, header in enumerate(headers):
            self.cell(col_widths[i], header_height, header, 1, 0, 'C')
        self.ln(header_height)

        # Data
        self.set_font('DejaVu', '', 7) # Reduced size
        for row in data:
            # Calculate max height needed for this row
            max_h = cell_height
            for i, item in enumerate(row):
                 # Estimate number of lines needed for multi_cell
                 lines = self.multi_cell(col_widths[i], cell_height, str(item), border=0, align='L', dry_run=True, output='LINES')
                 h = len(lines) * cell_height * line_height_ratio
                 max_h = max(max_h, h)

            # Check if the row fits on the current page BEFORE drawing it
            if self.get_y() + max_h > self.page_break_trigger:
                self.add_page() # Add page break BEFORE drawing the row

            # Draw the row cells using the calculated max_h
            current_y = self.get_y() # Store Y position at the start of the row
            for i, item in enumerate(row):
                 x = self.get_x()
                 # Draw the cell using multi_cell to handle wrapping
                 self.multi_cell(col_widths[i], cell_height, str(item), border=1, align='L' if isinstance(item, str) else 'R', max_line_height=cell_height, new_x="RIGHT", new_y="TOP")
                 # Reset Y to the starting Y of the row for the next cell
                 self.set_y(current_y)
                 # Set X for the next cell
                 self.set_x(x + col_widths[i])

            # Move down by the calculated max height for the row
            self.ln(max_h)
        self.ln(2) # Reduced space after table


    def write_key_value(self, key, value):
        cell_height = 4.5 # Reduced cell height
        self.set_font('DejaVu', 'B', 8) # Reduced size
        # Check page break before drawing key/value pair
        # Estimate height needed for value (assume 1 line unless long)
        value_str = str(value)
        needed_h = cell_height
        if isinstance(value, str) and len(value) > 90: # Adjusted heuristic
             lines = self.multi_cell(self.w - self.l_margin - self.r_margin - 35, cell_height, value_str, border=0, dry_run=True, output='LINES')
             needed_h = max(cell_height, len(lines) * cell_height)

        if self.get_y() + needed_h > self.page_break_trigger:
            self.add_page()

        self.cell(35, cell_height, key, border='B') # Reduced width slightly
        self.set_font('DejaVu', '', 8) # Reduced size
        # Use multi_cell for potentially long values like reasoning
        if isinstance(value, str) and len(value) > 90: # Adjusted heuristic
            x = self.get_x() # Get current X position before multi_cell
            self.multi_cell(0, cell_height, value_str, border='B', align='L') # Use remaining width
            # multi_cell moves Y, X might reset, which is fine here
        else:
            self.cell(0, cell_height, value_str, border='B', ln=1) # Move to next line


def save_analysis_to_pdf(result: dict, filename: str = "ai_hedge_fund_report.pdf") -> None:
    """
    Saves the trading analysis results to a PDF file.

    Args:
        result (dict): Dictionary containing decisions and analyst signals.
        filename (str): The name of the output PDF file.
    """
    decisions = result.get("decisions")
    analyst_signals_data = result.get("analyst_signals", {})
    if not decisions:
        print(f"{Fore.RED}No trading decisions available to save to PDF.{Style.RESET_ALL}")
        return

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Analysis per Ticker ---
    pdf.chapter_title("Ticker Analysis")

    for ticker, decision in decisions.items():
        pdf.section_title(f"Analysis for {ticker}")

        # Agent Analysis Table
        pdf.set_font('DejaVu', 'B', 9) # Reduced size
        pdf.cell(0, 5, "Agent Analysis:", 0, 1) # Reduced height
        agent_headers = ["Agent", "Signal", "Confidence", "Reasoning"]
        # Estimate column widths (total width ~190 for A4 portrait)
        agent_col_widths = [40, 20, 25, 105]
        agent_table_data = []

        # Sort agents for consistent order in PDF
        sorted_agent_keys = sorted(
            analyst_signals_data.keys(),
            key=lambda k: {name: idx for idx, (_, name) in enumerate(ANALYST_ORDER)}.get(k.replace('_agent', ''), 999)
        )

        for agent_key in sorted_agent_keys:
            signals = analyst_signals_data.get(agent_key, {})
            if ticker not in signals:
                continue
            if agent_key == "risk_management_agent": # Skip risk agent here
                 continue

            signal_data = signals[ticker]
            agent_name = agent_key.replace("_agent", "").replace("_", " ").title()
            signal_type = signal_data.get("signal", "").upper()
            confidence = f"{signal_data.get('confidence', 0):.1f}%"
            reasoning = signal_data.get("reasoning", "")
            # Basic text wrapping for PDF cell
            # Ensure reasoning is a string before wrapping
            wrapped_reasoning = '\n'.join(textwrap.wrap(str(reasoning), width=65)) # Adjusted width for smaller font

            agent_table_data.append([agent_name, signal_type, confidence, wrapped_reasoning])

        if agent_table_data:
            pdf.write_table(agent_headers, agent_table_data, agent_col_widths)
        else:
             pdf.set_font('DejaVu', '', 8) # Reduced size
             pdf.cell(0, 4, "No analyst signals available for this ticker.", 0, 1) # Reduced height
             pdf.ln(2) # Reduced spacing


        # Trading Decision
        pdf.set_font('DejaVu', 'B', 9) # Reduced size
        pdf.cell(0, 5, "Trading Decision:", 0, 1) # Reduced height
        pdf.write_key_value("Action", decision.get("action", "N/A").upper())
        pdf.write_key_value("Quantity", str(decision.get("quantity", "N/A")))
        pdf.write_key_value("Confidence", f"{decision.get('confidence', 0):.1f}%")
        pdf.write_key_value("Reasoning", str(decision.get("reasoning", "N/A")))
        pdf.ln(3) # Reduced spacing

    # --- Portfolio Summary ---
    pdf.add_page()
    pdf.chapter_title("Portfolio Summary")

    # Portfolio Decisions Table
    pdf.set_font('DejaVu', 'B', 9) # Reduced size
    pdf.cell(0, 5, "Decisions Summary:", 0, 1) # Reduced height
    summary_headers = ["Ticker", "Action", "Quantity", "Confidence"]
    summary_col_widths = [40, 40, 40, 40]
    summary_table_data = []
    portfolio_manager_reasoning = None

    for ticker, decision in decisions.items():
        # Capture portfolio manager reasoning (assuming it's the same in all decisions)
        if not portfolio_manager_reasoning and decision.get("reasoning"):
             portfolio_manager_reasoning = str(decision.get("reasoning", "N/A"))

        summary_table_data.append([
            ticker,
            decision.get("action", "N/A").upper(),
            str(decision.get("quantity", "N/A")),
            f"{decision.get('confidence', 0):.1f}%"
        ])

    pdf.write_table(summary_headers, summary_table_data, summary_col_widths)

    # Portfolio Strategy Reasoning
    if portfolio_manager_reasoning:
        pdf.set_font('DejaVu', 'B', 9) # Reduced size
        pdf.cell(0, 5, "Portfolio Strategy:", 0, 1) # Reduced height
        pdf.set_font('DejaVu', '', 8) # Reduced size
        pdf.multi_cell(0, 4.5, portfolio_manager_reasoning) # Reduced height
        pdf.ln(3) # Reduced spacing

    # --- Save PDF ---
    try:
        pdf.output(filename, "F")
        print(f"\n{Fore.GREEN}Successfully saved analysis report to: {filename}{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Error saving PDF report to {filename}: {e}{Style.RESET_ALL}")

# --- End PDF Generation Function ---
