import express from "express";
import cors from "cors";
import pLimit from "p-limit";
import { NSE } from "nse-bse-api";

const app = express();
app.use(cors());
app.use(express.json({ limit: "2mb" }));

const PORT = process.env.PORT || 5055;
const nse = new NSE();
const limit = pLimit(8);

function normalizeHistorical(raw, symbol) {
  if (!raw) return [];

  const rows =
    raw.data ||
    raw.candles ||
    raw.priceData ||
    raw.historical ||
    raw.records ||
    raw.grapthData ||
    [];

  return rows
    .map((r) => {
      if (!Array.isArray(r)) {
        const dt =
          r.date || r.datetime || r.timestamp || r.time || r.tradeDate || null;

        const open = Number(r.open ?? r.o ?? 0);
        const high = Number(r.high ?? r.h ?? 0);
        const low = Number(r.low ?? r.l ?? 0);
        const close = Number(r.close ?? r.c ?? 0);
        const volume = Number(r.volume ?? r.v ?? 0);

        if (!dt || !close) return null;

        return {
          symbol,
          date: dt,
          open,
          high,
          low,
          close,
          volume,
        };
      }

      if (r.length >= 6) {
        return {
          symbol,
          date: r[0],
          open: Number(r[1] ?? 0),
          high: Number(r[2] ?? 0),
          low: Number(r[3] ?? 0),
          close: Number(r[4] ?? 0),
          volume: Number(r[5] ?? 0),
        };
      }

      return null;
    })
    .filter(Boolean);
}

async function fetchHistory(symbol, from, to) {
  const methodCandidates = [
    "equityHistoricalData",
    "historicalData",
    "history",
    "getHistoricalData",
    "equityHistory",
  ];

  let raw = null;
  let lastErr = null;

  for (const methodName of methodCandidates) {
    if (typeof nse[methodName] === "function") {
      try {
        raw = await nse[methodName](symbol, from, to);
        if (raw) break;
      } catch (err) {
        lastErr = err;
      }
    }
  }

  if (!raw) {
    throw new Error(
      `No historical method succeeded for ${symbol}${lastErr ? `: ${lastErr.message}` : ""}`
    );
  }

  return normalizeHistorical(raw, symbol);
}

app.get("/health", (_, res) => {
  res.json({ ok: true, service: "market-bridge" });
});

app.post("/batch-history", async (req, res) => {
  const { symbols = [], from, to } = req.body || {};

  if (!Array.isArray(symbols) || symbols.length === 0) {
    return res.status(400).json({ ok: false, error: "symbols must be a non-empty array" });
  }

  const tasks = symbols.map((symbol) =>
    limit(async () => {
      try {
        const rows = await fetchHistory(symbol, from, to);
        return { symbol, ok: true, rows };
      } catch (err) {
        return { symbol, ok: false, rows: [], error: err.message };
      }
    })
  );

  const results = await Promise.all(tasks);

  res.json({
    ok: true,
    count: results.length,
    results,
  });
});

app.get("/quote/:symbol", async (req, res) => {
  const symbol = req.params.symbol;

  try {
    if (typeof nse.equityQuote !== "function") {
      return res.status(500).json({
        ok: false,
        symbol,
        error: "equityQuote method not available on installed package version",
      });
    }

    const quote = await nse.equityQuote(symbol);
    res.json({ ok: true, symbol, quote });
  } catch (err) {
    res.status(500).json({ ok: false, symbol, error: err.message });
  }
});

process.on("SIGINT", async () => {
  try {
    if (typeof nse.exit === "function") {
      await nse.exit();
    }
  } catch (_) {}
  process.exit(0);
});

process.on("SIGTERM", async () => {
  try {
    if (typeof nse.exit === "function") {
      await nse.exit();
    }
  } catch (_) {}
  process.exit(0);
});

app.listen(PORT, () => {
  console.log(`market bridge running on http://localhost:${PORT}`);
});
