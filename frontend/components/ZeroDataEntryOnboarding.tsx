"use client";

import { useMemo, useState, type CSSProperties } from "react";

type OperatingExpenseRow = {
  expense_type: string;
  amount: number;
};

type SupplierInvoiceRow = {
  item_category: string;
  item_name: string;
  quantity: number;
  unit: string;
  unit_cost: number;
  total_amount: number;
};

type ScannedDocument = {
  file_name: string;
  document_type: "pl_statement" | "supplier_invoice" | "mixed";
  operating_expenses: OperatingExpenseRow[];
  supplier_invoices: SupplierInvoiceRow[];
};

type ProcessResult = {
  summary_id: string;
  merchant_id: string;
  report_month: string;
  total_revenue: number;
  total_fixed_costs: number;
  total_ingredient_costs: number;
  net_profit: number;
  category_revenue: Record<string, number>;
  sales_logs_rows: number;
  operating_expenses_rows: number;
  supplier_invoices_rows: number;
};

type BoardroomStartResult = {
  merchant_id: string;
  target_month: string;
  financial_comparison: Record<string, unknown>;
  diagnostic_patterns: Record<string, unknown>;
  analyst_questions: string;
};

type BoardroomContinueResult = {
  merchant_id: string;
  target_month: string;
  merchant_profile: string;
  external_signals: Record<string, unknown>;
  theory_v1: string;
  supervisor_evaluation: string;
  supervisor_decision?: "APPROVED" | "REJECTED" | "UNKNOWN";
  final_approved_theory?: string;
  strategist_action_plan?: string;
};

type Props = {
  merchantId?: string;
};

type BoardroomStep = 1 | 2 | 3 | 4;

const API_BASE = "http://localhost:8001";

export default function ZeroDataEntryOnboarding({ merchantId }: Props) {
  const [merchantIdInput, setMerchantIdInput] = useState(merchantId || "");
  const [merchantProfile, setMerchantProfile] = useState("");
  const [reportMonth, setReportMonth] = useState("");

  const [statementFile, setStatementFile] = useState<File | null>(null);
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null);
  const [salesCsvFile, setSalesCsvFile] = useState<File | null>(null);

  const [scannedDocuments, setScannedDocuments] = useState<ScannedDocument[]>([]);
  const [scanErrors, setScanErrors] = useState<string[]>([]);

  const [scanLoading, setScanLoading] = useState<"statement" | "invoice" | null>(null);
  const [processing, setProcessing] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null);

  const [boardroomError, setBoardroomError] = useState<string | null>(null);
  const [boardroomSuccess, setBoardroomSuccess] = useState<string | null>(null);
  const [boardroomStartLoading, setBoardroomStartLoading] = useState(false);
  const [boardroomContinueLoading, setBoardroomContinueLoading] = useState(false);
  const [boardroomStartResult, setBoardroomStartResult] = useState<BoardroomStartResult | null>(null);
  const [bossAnswers, setBossAnswers] = useState("");
  const [boardroomContinueResult, setBoardroomContinueResult] = useState<BoardroomContinueResult | null>(null);
  const [boardroomStep, setBoardroomStep] = useState<BoardroomStep>(1);

  const totalsPreview = useMemo(() => {
    const fixedCosts = scannedDocuments
      .flatMap((d) => d.operating_expenses)
      .reduce((sum, row) => sum + toNumber(row.amount, 0), 0);

    const ingredientCosts = scannedDocuments
      .flatMap((d) => d.supplier_invoices)
      .reduce((sum, row) => sum + toNumber(row.total_amount, 0), 0);

    return {
      fixedCosts: round2(fixedCosts),
      ingredientCosts: round2(ingredientCosts),
    };
  }, [scannedDocuments]);

  const scanSingleDocument = async (file: File, scanKind: "statement" | "invoice") => {
    setError(null);
    setSuccessMessage(null);
    setProcessResult(null);

    if (!merchantIdInput.trim()) {
      setError("merchant_id is required.");
      return;
    }

    if (!merchantProfile.trim()) {
      setError("Please enter a 3-sentence merchant profile.");
      return;
    }

    try {
      setScanLoading(scanKind);

      const fileDataUrl = await fileToDataUrl(file);
      const res = await fetch(API_BASE + "/analyze-financial-document", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: file.name, file_data_url: fileDataUrl }),
      });

      const body = await safeParseJson(res);
      if (!res.ok) {
        throw new Error(body?.detail || `Failed to scan ${file.name}`);
      }

      const scannedDoc: ScannedDocument = {
        file_name: body.file_name,
        document_type: body.document_type,
        operating_expenses: body.operating_expenses || [],
        supplier_invoices: body.supplier_invoices || [],
      };

      setScannedDocuments((prev) => {
        const filtered = prev.filter((d) => d.file_name !== scannedDoc.file_name);
        return [...filtered, scannedDoc];
      });

      setScanErrors((prev) => prev.filter((msg) => !msg.startsWith(`${file.name}:`)));
      setSuccessMessage(`Scanned ${file.name} successfully.`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected error while scanning file.";
      setError(message);
      setScanErrors((prev) => [...prev, `${file.name}: ${message}`]);
    } finally {
      setScanLoading(null);
    }
  };

  const handleScanStatement = async () => {
    if (!statementFile) {
      setError("Please choose a statement file first.");
      return;
    }
    await scanSingleDocument(statementFile, "statement");
  };

  const handleScanInvoice = async () => {
    if (!invoiceFile) {
      setError("Please choose an invoice file first.");
      return;
    }
    await scanSingleDocument(invoiceFile, "invoice");
  };

  const handleProcessMonthlyUpload = async () => {
    setError(null);
    setSuccessMessage(null);
    setProcessResult(null);

    if (!merchantIdInput.trim()) {
      setError("merchant_id is required.");
      return;
    }

    if (!merchantProfile.trim()) {
      setError("Please enter a 3-sentence merchant profile.");
      return;
    }

    if (!reportMonth.trim()) {
      setError("report_month is required (YYYY-MM).");
      return;
    }

    if (!salesCsvFile) {
      setError("Please upload Sales Records CSV.");
      return;
    }

    try {
      setProcessing(true);
      const salesCsvDataUrl = await fileToDataUrl(salesCsvFile);

      const payload = {
        merchant_id: merchantIdInput.trim(),
        merchant_profile: merchantProfile.trim(),
        report_month: reportMonth.trim(),
        scanned_documents: scannedDocuments,
        sales_csv_data_url: salesCsvDataUrl,
      };

      const res = await fetch(API_BASE + "/process-monthly-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const body = await safeParseJson(res);
      if (!res.ok) {
        throw new Error(body?.detail || "Failed to process monthly upload.");
      }

      setProcessResult(body as ProcessResult);
      setSuccessMessage("Monthly reconciliation completed and saved to Supabase.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error while processing monthly upload.");
    } finally {
      setProcessing(false);
    }
  };

  const handleBoardroomStart = async () => {
    setBoardroomError(null);
    setBoardroomSuccess(null);
    setBoardroomStartResult(null);
    setBoardroomContinueResult(null);
    setBoardroomStep(1);

    if (!merchantIdInput.trim()) {
      setBoardroomError("merchant_id is required for boardroom audit.");
      return;
    }

    if (!reportMonth.trim()) {
      setBoardroomError("report_month is required for boardroom audit (YYYY-MM).");
      return;
    }

    try {
      setBoardroomStartLoading(true);
      const res = await fetch(API_BASE + "/boardroom/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          merchant_id: merchantIdInput.trim(),
          target_month: reportMonth.trim(),
        }),
      });

      const body = await safeParseJson(res);
      if (!res.ok) {
        throw new Error(body?.detail || "Failed to start boardroom audit.");
      }

      setBoardroomStartResult(body as BoardroomStartResult);
      setBossAnswers("");
      setBoardroomStep(2);
      setBoardroomSuccess("Step 1 completed. Proceed to Step 2: answer Analyst questions.");
    } catch (err) {
      setBoardroomError(err instanceof Error ? err.message : "Unexpected error starting boardroom audit.");
    } finally {
      setBoardroomStartLoading(false);
    }
  };

  const handleBoardroomContinue = async () => {
    setBoardroomError(null);
    setBoardroomSuccess(null);
    setBoardroomContinueResult(null);

    if (!merchantIdInput.trim()) {
      setBoardroomError("merchant_id is required for boardroom audit.");
      return;
    }

    if (!reportMonth.trim()) {
      setBoardroomError("report_month is required for boardroom audit (YYYY-MM).");
      return;
    }

    if (!boardroomStartResult) {
      setBoardroomError("Please run Start Boardroom Audit first.");
      return;
    }

    if (!bossAnswers.trim()) {
      setBoardroomError("Please answer the Analyst questions before continuing.");
      return;
    }

    try {
      setBoardroomContinueLoading(true);
      const res = await fetch(API_BASE + "/boardroom/continue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          merchant_id: merchantIdInput.trim(),
          target_month: reportMonth.trim(),
          boss_answers: bossAnswers.trim(),
        }),
      });

      const body = await safeParseJson(res);
      if (!res.ok) {
        throw new Error(body?.detail || "Failed to continue boardroom audit.");
      }

      const result = body as BoardroomContinueResult;
      setBoardroomContinueResult(result);
      setBoardroomStep(3);

      const decision = String(result.supervisor_decision || "UNKNOWN").toUpperCase();
      if (decision === "APPROVED") {
        setBoardroomSuccess("Step 2 completed. Step 3 approved. Proceed to Step 4 for strategic action plan.");
      } else if (decision === "REJECTED") {
        setBoardroomSuccess("Step 2 completed. Step 3 rejected by Supervisor. Strategy step is locked.");
      } else {
        setBoardroomSuccess("Step 2 completed. Step 3 completed with unknown supervisor decision.");
      }
    } catch (err) {
      setBoardroomError(err instanceof Error ? err.message : "Unexpected error continuing boardroom audit.");
    } finally {
      setBoardroomContinueLoading(false);
    }
  };

  const proceedToStrategyStep = () => {
    if (!boardroomContinueResult) {
      setBoardroomError("Complete Step 3 first.");
      return;
    }

    const decision = String(boardroomContinueResult.supervisor_decision || "UNKNOWN").toUpperCase();
    if (decision !== "APPROVED") {
      setBoardroomError("Step 4 is available only when Supervisor decision is APPROVED.");
      return;
    }

    if (!boardroomContinueResult.strategist_action_plan) {
      setBoardroomError("No strategist plan found. Retry Step 2 and Step 3.");
      return;
    }

    setBoardroomError(null);
    setBoardroomStep(4);
    setBoardroomSuccess("Step 3 completed. Proceeding to Step 4 strategist action plan.");
  };

  const resetBoardroomFlow = () => {
    setBoardroomStep(1);
    setBoardroomError(null);
    setBoardroomSuccess(null);
    setBoardroomStartResult(null);
    setBoardroomContinueResult(null);
    setBossAnswers("");
  };

  const getBoardroomStepStatus = (step: BoardroomStep): "done" | "active" | "pending" => {
    if (boardroomStep > step) return "done";
    if (boardroomStep === step) return "active";
    return "pending";
  };

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.heading}>Monthly Financial Upload</h2>
      <p style={styles.subheading}>Tauke.ai AI-CFO Pipeline: Scan P&L + Invoices, then reconcile with Sales CSV.</p>

      <section style={styles.card}>
        <h3 style={styles.sectionHeading}>Phase 0: Merchant Setup</h3>
        <label style={styles.label}>merchant_id</label>
        <input
          style={styles.input}
          value={merchantIdInput}
          onChange={(e) => setMerchantIdInput(e.target.value)}
          placeholder="e.g. c6417c1f-56ee-4f6a-bab8-def781d9418f"
        />

        <label style={styles.label}>Merchant Profile (3 sentences: F&B Type, Location, Audience)</label>
        <textarea
          style={styles.textarea}
          rows={4}
          value={merchantProfile}
          onChange={(e) => setMerchantProfile(e.target.value)}
          placeholder="Example: We are a campus kopitiam serving coffee and rice bowls. We are located near UM lecture halls. Our main audience is students and campus staff."
        />

        <label style={styles.label}>report_month (YYYY-MM)</label>
        <input
          style={styles.input}
          value={reportMonth}
          onChange={(e) => setReportMonth(e.target.value)}
          placeholder="2026-04"
        />
      </section>

      <section style={styles.card}>
        <h3 style={styles.sectionHeading}>Phase 1: Upload & Scan Financial Documents</h3>
        <p style={styles.hint}>Upload and scan statements and invoices separately.</p>

        <label style={styles.label}>P&L Statement (image/pdf)</label>
        <input
          style={styles.input}
          type="file"
          accept=".pdf,image/png,image/jpeg,image/jpg"
          onChange={(e) => setStatementFile(e.target.files?.[0] || null)}
        />
        <button style={styles.button} onClick={handleScanStatement} disabled={scanLoading !== null}>
          {scanLoading === "statement" ? "Scanning Statement..." : "Upload Statement"}
        </button>

        {statementFile ? <p style={styles.meta}>Statement file: {statementFile.name}</p> : null}

        <label style={styles.label}>Supplier Invoice / SOA (image/pdf)</label>
        <input
          style={styles.input}
          type="file"
          accept=".pdf,image/png,image/jpeg,image/jpg"
          onChange={(e) => setInvoiceFile(e.target.files?.[0] || null)}
        />

        <button style={styles.button} onClick={handleScanInvoice} disabled={scanLoading !== null}>
          {scanLoading === "invoice" ? "Scanning Invoice..." : "Upload Invoice"}
        </button>

        {invoiceFile ? <p style={styles.meta}>Invoice file: {invoiceFile.name}</p> : null}

        {scanErrors.length ? (
          <div style={styles.warnBox}>
            {scanErrors.map((msg) => (
              <div key={msg}>- {msg}</div>
            ))}
          </div>
        ) : null}
      </section>

      <section style={styles.card}>
        <h3 style={styles.sectionHeading}>Phase 2: Sales Records CSV</h3>
        <p style={styles.hint}>Upload monthly sales CSV to calculate total_revenue and category_revenue.</p>
        <input
          style={styles.input}
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setSalesCsvFile(e.target.files?.[0] || null)}
        />

        {salesCsvFile ? <p style={styles.meta}>Sales CSV: {salesCsvFile.name}</p> : null}
      </section>

      <section style={styles.card}>
        <h3 style={styles.sectionHeading}>Scanned Output Preview</h3>
        <p style={styles.meta}>P&L rows: {scannedDocuments.flatMap((d) => d.operating_expenses).length}</p>
        <p style={styles.meta}>Invoice rows: {scannedDocuments.flatMap((d) => d.supplier_invoices).length}</p>
        <p style={styles.meta}>Estimated fixed costs: RM {totalsPreview.fixedCosts.toFixed(2)}</p>
        <p style={styles.meta}>Estimated ingredient costs: RM {totalsPreview.ingredientCosts.toFixed(2)}</p>

        {scannedDocuments.length ? (
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Rows Extracted</th>
                </tr>
              </thead>
              <tbody>
                {scannedDocuments.map((doc) => (
                  <tr key={doc.file_name}>
                    <td>{doc.file_name}</td>
                    <td>{doc.document_type}</td>
                    <td>
                      {doc.document_type === "pl_statement"
                        ? doc.operating_expenses.length
                        : doc.document_type === "supplier_invoice"
                          ? doc.supplier_invoices.length
                          : doc.operating_expenses.length + doc.supplier_invoices.length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={styles.hint}>No scanned output yet.</p>
        )}

        <button style={styles.button} onClick={handleProcessMonthlyUpload} disabled={processing}>
          {processing ? "Processing..." : "Process Monthly Upload"}
        </button>
      </section>

      {error ? <div style={styles.error}>{error}</div> : null}
      {successMessage ? <div style={styles.success}>{successMessage}</div> : null}

      {processResult ? (
        <section style={styles.card}>
          <h3 style={styles.sectionHeading}>Monthly Summary Saved</h3>
          <div style={styles.kv}>summary_id: {processResult.summary_id}</div>
          <div style={styles.kv}>merchant_id: {processResult.merchant_id}</div>
          <div style={styles.kv}>report_month: {processResult.report_month}</div>
          <div style={styles.kv}>total_revenue: RM {processResult.total_revenue.toFixed(2)}</div>
          <div style={styles.kv}>total_fixed_costs: RM {processResult.total_fixed_costs.toFixed(2)}</div>
          <div style={styles.kv}>total_ingredient_costs: RM {processResult.total_ingredient_costs.toFixed(2)}</div>
          <div style={styles.kv}>net_profit: RM {processResult.net_profit.toFixed(2)}</div>
          <div style={styles.kv}>sales_logs rows: {processResult.sales_logs_rows}</div>
          <div style={styles.kv}>operating_expenses rows: {processResult.operating_expenses_rows}</div>
          <div style={styles.kv}>supplier_invoices rows: {processResult.supplier_invoices_rows}</div>
        </section>
      ) : null}

      <section style={styles.card}>
        <h3 style={styles.sectionHeading}>Phase 3: Boardroom Agentic Audit</h3>
        <p style={styles.hint}>Each step unlocks the next one after completion.</p>

        <div style={styles.stepRow}>
          <div
            style={{
              ...styles.stepPill,
              ...(getBoardroomStepStatus(1) === "done"
                ? styles.stepPillDone
                : getBoardroomStepStatus(1) === "active"
                  ? styles.stepPillActive
                  : styles.stepPillPending),
            }}
          >
            Step 1: Interrogation
          </div>
          <div
            style={{
              ...styles.stepPill,
              ...(getBoardroomStepStatus(2) === "done"
                ? styles.stepPillDone
                : getBoardroomStepStatus(2) === "active"
                  ? styles.stepPillActive
                  : styles.stepPillPending),
            }}
          >
            Step 2: Boss Input
          </div>
          <div
            style={{
              ...styles.stepPill,
              ...(getBoardroomStepStatus(3) === "done"
                ? styles.stepPillDone
                : getBoardroomStepStatus(3) === "active"
                  ? styles.stepPillActive
                  : styles.stepPillPending),
            }}
          >
            Step 3: Final Review
          </div>
          <div
            style={{
              ...styles.stepPill,
              ...(getBoardroomStepStatus(4) === "done"
                ? styles.stepPillDone
                : getBoardroomStepStatus(4) === "active"
                  ? styles.stepPillActive
                  : styles.stepPillPending),
            }}
          >
            Step 4: Strategy Plan
          </div>
        </div>

        {boardroomStep === 1 ? (
          <div style={styles.chatBlock}>
            <div style={styles.chatTitle}>Step 1 Active: Generate Analyst Questions</div>
            <p style={styles.meta}>Click start to run interrogation and move to Step 2.</p>
            <button
              style={styles.button}
              onClick={handleBoardroomStart}
              disabled={boardroomStartLoading || boardroomContinueLoading}
            >
              {boardroomStartLoading ? "Starting Step 1..." : "Start Step 1"}
            </button>
          </div>
        ) : null}

        {boardroomStep === 2 && boardroomStartResult ? (
          <div style={styles.resultStack}>
            <div style={styles.info}>Step 1 completed. Proceeding to Step 2.</div>

            <div style={styles.chatBlock}>
              <div style={styles.chatTitle}>Analyst Questions</div>
              <pre style={styles.preWrap}>{boardroomStartResult.analyst_questions}</pre>
            </div>

            <div style={styles.chatBlock}>
              <div style={styles.chatTitle}>Step 2 Active: Boss Answers</div>
              <label style={styles.label}>Boss Answers</label>
              <textarea
                style={styles.textarea}
                rows={5}
                value={bossAnswers}
                onChange={(e) => setBossAnswers(e.target.value)}
                placeholder="Answer Analyst questions here, briefly and directly."
              />

              <button
                style={styles.button}
                onClick={handleBoardroomContinue}
                disabled={boardroomContinueLoading || boardroomStartLoading}
              >
                {boardroomContinueLoading ? "Running Step 2..." : "Submit Answers and Go to Step 3"}
              </button>
            </div>
          </div>
        ) : null}

        {boardroomStep === 3 && boardroomContinueResult ? (
          <div style={styles.resultStack}>
            <div style={styles.info}>Step 2 completed. Proceeding to Step 3.</div>

            <div style={styles.chatBlock}>
              <div style={styles.chatTitle}>Analyst Theory V1</div>
              <pre style={styles.preWrap}>{boardroomContinueResult.theory_v1}</pre>
            </div>

            <div style={styles.chatBlock}>
              <div style={styles.chatTitle}>Supervisor Evaluation</div>
              <pre style={styles.preWrap}>{boardroomContinueResult.supervisor_evaluation}</pre>
            </div>

            <div style={styles.chatBlock}>
              <div style={styles.chatTitle}>Step 3 Status</div>
              <div style={styles.meta}>Supervisor decision: {boardroomContinueResult.supervisor_decision || "UNKNOWN"}</div>

              {String(boardroomContinueResult.supervisor_decision || "UNKNOWN").toUpperCase() === "APPROVED" ? (
                <>
                  <div style={styles.info}>Step 3 completed and approved. Proceed to Step 4.</div>
                  <button style={styles.button} onClick={proceedToStrategyStep}>
                    Proceed to Step 4
                  </button>
                </>
              ) : (
                <div style={styles.warnBox}>Step 4 is locked because Supervisor did not approve in Step 3.</div>
              )}
            </div>
          </div>
        ) : null}

        {boardroomStep === 4 && boardroomContinueResult ? (
          <div style={styles.resultStack}>
            <div style={styles.info}>Step 3 completed. Proceeding to Step 4.</div>
            <div style={styles.success}>Step 4 completed. Top 3 Strategic Action Plans generated.</div>

            <div style={styles.chatBlock}>
              <div style={styles.chatTitle}>Strategist Agent - Top 3 Strategic Action Plans</div>
              <pre style={styles.preWrap}>{boardroomContinueResult.strategist_action_plan || "No strategist output available."}</pre>
            </div>
          </div>
        ) : null}

        {boardroomError ? <div style={styles.error}>{boardroomError}</div> : null}
        {boardroomSuccess ? <div style={styles.success}>{boardroomSuccess}</div> : null}

        {boardroomStep > 1 ? (
          <button style={styles.secondaryButton} onClick={resetBoardroomFlow} disabled={boardroomStartLoading || boardroomContinueLoading}>
            Start New Boardroom Run
          </button>
        ) : null}
      </section>
    </div>
  );
}

async function safeParseJson(response: Response): Promise<any | null> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        resolve(result);
      } else {
        reject(new Error("Failed to read uploaded file."));
      }
    };
    reader.onerror = () => reject(new Error("Failed to read uploaded file."));
    reader.readAsDataURL(file);
  });
}

function toNumber(value: string | number | undefined | null, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

const styles: Record<string, CSSProperties> = {
  wrapper: {
    maxWidth: 1100,
    margin: "0 auto",
    padding: "24px",
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },
  heading: {
    marginBottom: 8,
  },
  sectionHeading: {
    margin: "0 0 8px 0",
  },
  subheading: {
    marginTop: 0,
    color: "#555",
  },
  card: {
    border: "1px solid #ddd",
    borderRadius: 10,
    padding: 16,
    marginTop: 16,
    background: "#fff",
  },
  label: {
    display: "block",
    marginBottom: 6,
    fontWeight: 600,
  },
  input: {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #bbb",
    marginBottom: 12,
  },
  textarea: {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #bbb",
    marginBottom: 12,
    resize: "vertical",
  },
  button: {
    padding: "10px 16px",
    borderRadius: 8,
    border: "none",
    background: "#0f766e",
    color: "#fff",
    cursor: "pointer",
    fontWeight: 600,
  },
  secondaryButton: {
    marginTop: 12,
    padding: "10px 16px",
    borderRadius: 8,
    border: "1px solid #94a3b8",
    background: "#fff",
    color: "#0f172a",
    cursor: "pointer",
    fontWeight: 600,
  },
  error: {
    background: "#fee2e2",
    color: "#991b1b",
    border: "1px solid #fecaca",
    borderRadius: 8,
    padding: 10,
    marginTop: 12,
  },
  success: {
    background: "#dcfce7",
    color: "#166534",
    border: "1px solid #bbf7d0",
    borderRadius: 8,
    padding: 10,
    marginTop: 12,
  },
  hint: {
    color: "#555",
    marginTop: 0,
  },
  meta: {
    color: "#333",
    margin: "8px 0",
  },
  tableWrap: {
    overflowX: "auto",
    marginBottom: 12,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  kv: {
    marginBottom: 6,
  },
  warnBox: {
    background: "#fff7ed",
    color: "#9a3412",
    border: "1px solid #fed7aa",
    borderRadius: 8,
    padding: 10,
    marginTop: 10,
  },
  chatBlock: {
    marginTop: 12,
    padding: 12,
    borderRadius: 8,
    border: "1px solid #d1d5db",
    background: "#f9fafb",
  },
  chatTitle: {
    fontWeight: 700,
    marginBottom: 8,
  },
  preWrap: {
    margin: 0,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace",
    fontSize: 13,
    lineHeight: 1.5,
  },
  resultStack: {
    display: "grid",
    gap: 12,
    marginTop: 12,
  },
  info: {
    background: "#eff6ff",
    color: "#1e3a8a",
    border: "1px solid #bfdbfe",
    borderRadius: 8,
    padding: 10,
    marginTop: 12,
  },
  stepRow: {
    display: "grid",
    gap: 8,
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    marginBottom: 12,
  },
  stepPill: {
    borderRadius: 999,
    padding: "8px 12px",
    fontWeight: 700,
    fontSize: 13,
    textAlign: "center",
  },
  stepPillDone: {
    background: "#dcfce7",
    color: "#166534",
    border: "1px solid #86efac",
  },
  stepPillActive: {
    background: "#ecfeff",
    color: "#155e75",
    border: "1px solid #67e8f9",
  },
  stepPillPending: {
    background: "#f3f4f6",
    color: "#4b5563",
    border: "1px solid #d1d5db",
  },
};
