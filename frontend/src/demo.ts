/** Browser-only UI preview. No fetch, uploads, external analysis or media processing. */
import type { Analysis, Asset, Choice, Task } from "./api";
import { sampleAssets } from "./demo-assets";

type RecordTask = Task & {
  readyAt: number;
  sampleResult: Task["result"];
  payload: Record<string, unknown>;
};
type Result = { status: number; body: unknown };
const key = "download-convert.demo.tasks.v1";
let records: RecordTask[] = [];
try {
  const saved = JSON.parse(localStorage.getItem(key) || "[]");
  if (Array.isArray(saved))
    records = saved
      .filter(
        (x) =>
          x &&
          /^[a-f0-9]{32}$/.test(x.id) &&
          typeof x.title === "string" &&
          x.title.startsWith("Demo · ") &&
          Number.isFinite(x.readyAt) &&
          ["analyze", "download", "convert"].includes(x.kind) &&
          ["queued", "running", "completed", "failed", "cancelled"].includes(
            x.state,
          ),
      )
      .slice(0, 30);
} catch {
  /* In-memory preview still works when browser storage is unavailable. */
}
const now = () => Date.now() / 1000;
function persist() {
  try {
    localStorage.setItem(key, JSON.stringify(records.slice(0, 30)));
  } catch {
    /* Optional persistence. */
  }
}
function publicTask(record: RecordTask): Task {
  const { readyAt, sampleResult, payload, ...task } = record;
  return task;
}
function update() {
  for (const record of records) {
    if (!["queued", "running"].includes(record.state)) continue;
    if (now() >= record.readyAt) {
      record.state = "completed";
      record.operation = "ready";
      record.progress = null;
      record.result = record.sampleResult;
    } else if (now() - record.created_at > 0.2) {
      record.state = "running";
      record.operation = "preparing";
      record.progress = null;
    }
  }
  persist();
}
function make(
  kind: Task["kind"],
  title: string,
  result: Task["result"],
  payload: Record<string, unknown> = {},
): Result {
  const record: RecordTask = {
    id: crypto.randomUUID().replaceAll("-", ""),
    kind,
    title: "Demo · " + title,
    state: "queued",
    operation: "queued",
    progress: null,
    speed: null,
    eta: null,
    created_at: now(),
    expires_at: null,
    expired: false,
    result: null,
    error: null,
    readyAt: now() + 1.2,
    sampleResult: result,
    payload,
  };
  records.unshift(record);
  records = records.slice(0, 30);
  persist();
  return { status: 202, body: publicTask(record) };
}
const fail = (): Result => ({
  status: 400,
  body: {
    detail: {
      code: "demo_only",
      message:
        "This preview uses prepared samples. Use the example buttons, or run the self-hosted service for your own links and files.",
    },
  },
});
function assetById(id: unknown): Asset | undefined {
  const value = Object.values(sampleAssets).find((asset) => asset.id === id);
  return value ? { ...value, expires_at: now() + 86400 } : undefined;
}
function choice(name: string, id: string): Choice {
  const a = sampleAssets[name];
  return {
    id,
    kind: "video",
    container: "mp4",
    width: a.metadata.width || null,
    height: a.metadata.height || null,
    fps: 12,
    video_codec: "h264",
    audio_codec: "aac",
    audio_bitrate: null,
    has_audio: true,
    operation: "download",
    size: a.size,
    size_kind: "exact",
    source_format_ids: ["prepared-sample"],
    format_note: "Demo sample",
  };
}
function analysis(photos: boolean): Analysis {
  return photos
    ? {
        kind: "photos",
        title: "Two generated sample images",
        platform: "Demo",
        author: "Owned test media",
        thumbnail: "/demo-assets/sample-image-1.png",
        duration: null,
        choices: [],
        item_count: 2,
        items: [1, 2].map((number) => {
          const a = sampleAssets[number === 1 ? "image1_png" : "image2_jpg"];
          return {
            id: "photo_" + number,
            position: number,
            width: a.metadata.width,
            height: a.metadata.height,
            format: a.metadata.format,
            size: a.size,
            preview_asset_id: a.id,
          };
        }),
      }
    : {
        kind: "video",
        title: "Generated motion and tone",
        platform: "Demo",
        author: "Owned test media",
        thumbnail: "/demo-assets/sample-poster.jpg",
        duration: sampleAssets.video.metadata.duration || 2,
        choices: [choice("video", "option_0"), choice("video_low", "option_1")],
      };
}
function conversionAsset(source: Asset, output: string) {
  const sourceName =
    Object.entries(sampleAssets).find(([, a]) => a.id === source.id)?.[0] || "";
  if (sourceName.startsWith("image"))
    return sampleAssets[sourceName.split("_")[0] + "_" + output];
  if (output === "mp3") return sampleAssets.mp3;
  if (output === "gif") return sampleAssets.gif;
  if (output === "mp4")
    return sampleAssets[
      sourceName.startsWith("gif") ? "gif_mp4" : "converted_mp4"
    ];
}
export async function demoRequest(
  path: string,
  init?: RequestInit,
): Promise<Result> {
  update();
  const method = init?.method || "GET";
  if (path === "/uploads") return fail();
  let body: Record<string, any> = {};
  try {
    if (typeof init?.body === "string") body = JSON.parse(init.body);
  } catch {
    return fail();
  }
  if (path === "/health")
    return { status: 200, body: { status: "demo", worker_online: true } };
  if (path === "/settings")
    return {
      status: 200,
      body: {
        versions: {},
        source_transport: { browser_impersonation: false },
        worker_online: true,
        ttl_seconds: 86400,
        job_timeout_seconds: 1800,
        max_file_bytes: 536870912,
        max_storage_bytes: 5368709120,
        used_bytes: 0,
        concurrency: 1,
        cookies_configured: false,
        platforms: [],
        presets: [],
      },
    };
  if (path === "/tasks" && method === "GET")
    return { status: 200, body: records.map(publicTask) };
  if (path === "/demo/reset" && method === "POST") {
    records = [];
    persist();
    return { status: 200, body: {} };
  }
  if (/^\/assets\/[a-f0-9]{32}$/.test(path)) {
    const asset = assetById(path.split("/")[2]);
    return asset ? { status: 200, body: asset } : fail();
  }
  if (path === "/analyze" && method === "POST") {
    if (
      !["https://demo.invalid/video", "https://demo.invalid/photos"].includes(
        body.url,
      )
    )
      return fail();
    return make(
      "analyze",
      "Load prepared example",
      analysis(body.url.endsWith("photos")),
      body,
    );
  }
  if (path === "/downloads" && method === "POST") {
    const record = records.find(
      (x) => x.id === body.analysis_id && x.state === "completed",
    );
    if (
      !record ||
      record.result?.kind !== "video" ||
      !["option_0", "option_1"].includes(body.choice_id) ||
      !["original", "compatible", "mp3"].includes(body.profile) ||
      (body.profile === "mp3" && Number(body.bitrate) !== 192)
    )
      return fail();
    const asset =
      sampleAssets[
        body.profile === "mp3"
          ? "mp3"
          : body.choice_id === "option_1"
            ? "video_low"
            : "video"
      ];
    return make(
      "download",
      asset.name,
      { asset_id: asset.id, preview: false },
      body,
    );
  }
  if (path === "/photo-downloads" && method === "POST") {
    const record = records.find(
      (x) => x.id === body.analysis_id && x.state === "completed",
    );
    if (
      !record ||
      record.result?.kind !== "photos" ||
      !Array.isArray(body.item_ids) ||
      !body.item_ids.length ||
      body.item_ids.some((id: string) => !["photo_1", "photo_2"].includes(id))
    )
      return fail();
    const files = [1, 2]
      .filter((n) => body.item_ids.includes("photo_" + n))
      .map((n) => {
        const a = sampleAssets[n === 1 ? "image1_png" : "image2_jpg"];
        return {
          item_id: "photo_" + n,
          position: n,
          kind: "image",
          name: a.name,
          asset_id: a.id,
          preview_asset_id: a.id,
          width: a.metadata.width,
          height: a.metadata.height,
          format: a.metadata.format,
          size: a.size,
        };
      });
    return make(
      "download",
      "Prepared sample photos",
      {
        kind: "photos",
        files,
        archive_asset_id:
          files.length > 1 ? sampleAssets.photos_zip.id : undefined,
      },
      body,
    );
  }
  if (path === "/conversions" && method === "POST") {
    const source = assetById(body.asset_id),
      output = body.parameters?.output;
    if (
      !source ||
      !source.operations.some((x) => x.id === output) ||
      (output === "mp3" && Number(body.parameters?.bitrate) !== 192)
    )
      return fail();
    const asset = conversionAsset(source, output);
    if (!asset) return fail();
    return make(
      "convert",
      "Prepared " + output.toUpperCase() + " example",
      {
        asset_id: asset.id,
        preview: ["image", "animation"].includes(asset.metadata.kind),
      },
      body,
    );
  }
  const action = path.match(/^\/tasks\/([a-f0-9]{32})\/(cancel|retry)$/);
  if (action && method === "POST") {
    const record = records.find((x) => x.id === action[1]);
    if (!record) return fail();
    if (action[2] === "cancel") {
      if (!["queued", "running"].includes(record.state)) return fail();
      record.state = "cancelled";
      persist();
      return { status: 200, body: publicTask(record) };
    }
    if (!["cancelled", "failed"].includes(record.state)) return fail();
    return make(
      record.kind,
      record.title.replace(/^Demo · /, ""),
      record.sampleResult,
      record.payload,
    );
  }
  return fail();
}
