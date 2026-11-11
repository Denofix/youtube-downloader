<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import Icon from "./Icon.vue";
import {
  api,
  post,
  bytes,
  duration,
  date,
  active,
  type Analysis,
  type Asset,
  type Choice,
  type ServerSettings,
  type Task,
} from "./api";
type Tab = "download" | "convert" | "tasks" | "settings";
const tabs: Tab[] = ["download", "convert", "tasks", "settings"];
const tab = ref<Tab>(
  tabs.includes(location.hash.slice(1) as Tab)
    ? (location.hash.slice(1) as Tab)
    : "download",
);
const tasks = ref<Task[]>([]),
  server = ref<ServerSettings | null>(null);
const url = ref(""),
  error = ref(""),
  feedback = ref(""),
  busy = ref(false),
  connected = ref(false),
  worker = ref(false);
const analyzingId = ref(""),
  inspectingId = ref(""),
  analysisId = ref("");
const analysis = ref<Analysis | null>(null),
  choiceId = ref(""),
  profile = ref("original"),
  bitrate = ref(192);
const asset = ref<Asset | null>(null),
  output = ref(""),
  fileInput = ref<HTMLInputElement | null>(null);
const gifStart = ref(0),
  gifDuration = ref(5),
  gifFps = ref(12),
  gifWidth = ref(480),
  dragging = ref(false);
const activeTasks = computed(() => tasks.value.filter(active)),
  history = computed(() => tasks.value.filter((t) => !active(t)));
const choice = computed(() =>
  analysis.value?.choices.find((c) => c.id === choiceId.value),
);
let timer: ReturnType<typeof setInterval> | undefined,
  polling = false;
function navigate(target: Tab) {
  tab.value = target;
  location.hash = target;
  error.value = "";
  feedback.value = "";
}
function syncHash() {
  const next = location.hash.slice(1) as Tab;
  if (tabs.includes(next)) tab.value = next;
}
function choiceLabel(c: Choice) {
  const details = [
    c.kind === "video" ? (c.height ? c.height + "p" : "Video") : "Audio",
    c.fps ? c.fps + " fps" : null,
    c.container.toUpperCase(),
    c.kind === "audio" && c.audio_bitrate ? c.audio_bitrate + " kbps" : null,
    c.kind === "video" ? (c.has_audio ? "with audio" : "no audio") : null,
    c.video_codec || c.audio_codec,
    c.format_note,
    c.source_format_ids.join(" + "),
  ];
  return details.filter(Boolean).join(" · ");
}
function useAnalysis(task: Task) {
  if (!task.result?.choices || task.expired) {
    error.value = "This analysis has expired. Analyze again.";
    return;
  }
  analysis.value = task.result as Analysis;
  analysisId.value = task.id;
  const ordered = [...analysis.value.choices].sort(
    (a, b) =>
      (b.height || 0) - (a.height || 0) ||
      (b.fps || 0) - (a.fps || 0) ||
      (b.audio_bitrate || 0) - (a.audio_bitrate || 0),
  );
  choiceId.value = (ordered.find((c) => c.has_audio) || ordered[0])?.id || "";
  profile.value = "original";
}
async function loadAsset(id: string) {
  asset.value = await api<Asset>("/assets/" + id);
  output.value = asset.value.operations[0]?.id || "";
  gifDuration.value = Math.min(5, asset.value.metadata.duration || 5);
}
async function refresh() {
  if (polling) return;
  polling = true;
  try {
    const [list, health] = await Promise.all([
      api<Task[]>("/tasks"),
      api<{ worker_online: boolean }>("/health"),
    ]);
    tasks.value = list;
    connected.value = true;
    worker.value = health.worker_online;
    for (const [id, kind] of [
      [analyzingId.value, "analysis"],
      [inspectingId.value, "inspect"],
    ]) {
      const task = list.find((t) => t.id === id);
      if (!id || !task || active(task)) continue;
      if (kind === "analysis") {
        analyzingId.value = "";
        if (task.state === "completed") useAnalysis(task);
      } else {
        inspectingId.value = "";
        if (task.result?.asset_id) {
          try {
            await loadAsset(task.result.asset_id);
          } catch (err) {
            error.value = (err as Error).message;
          }
        }
      }
      if (task.error) error.value = task.error.message;
    }
  } catch {
    connected.value = false;
  } finally {
    polling = false;
  }
}
async function action(work: () => Promise<void>) {
  busy.value = true;
  error.value = "";
  feedback.value = "";
  try {
    await work();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Something went wrong.";
  } finally {
    busy.value = false;
  }
}
async function analyze() {
  await action(async () => {
    analysis.value = null;
    analyzingId.value = (await post<Task>("/analyze", { url: url.value })).id;
    await refresh();
  });
}
async function download() {
  await action(async () => {
    await post("/downloads", {
      analysis_id: analysisId.value,
      choice_id: choiceId.value,
      profile: profile.value,
      bitrate: bitrate.value,
    });
    navigate("tasks");
    await refresh();
    feedback.value = "Download added to the queue.";
  });
}
async function upload(files: FileList | File[] | null) {
  const file = files?.[0];
  if (!file) return;
  if (files!.length > 1) {
    error.value =
      "This build accepts one file at a time. Upload additional files separately.";
    return;
  }
  await action(async () => {
    if (server.value && file.size > server.value.max_file_bytes)
      throw new Error(
        "Upload limit: " + bytes(server.value.max_file_bytes) + ".",
      );
    asset.value = null;
    inspectingId.value = (
      await api<Task>("/uploads", {
        method: "POST",
        headers: {
          "X-Filename": encodeURIComponent(file.name),
          "Content-Type": "application/octet-stream",
        },
        body: file,
      })
    ).id;
    await refresh();
  });
}
function drop(event: DragEvent) {
  event.preventDefault();
  dragging.value = false;
  void upload(event.dataTransfer?.files || null);
}
async function convert() {
  await action(async () => {
    await post("/conversions", {
      asset_id: asset.value!.id,
      parameters: {
        output: output.value,
        bitrate: bitrate.value,
        start: gifStart.value,
        duration: gifDuration.value,
        fps: gifFps.value,
        width: gifWidth.value,
      },
    });
    navigate("tasks");
    await refresh();
    feedback.value = "Conversion added to the queue.";
  });
}
async function taskAction(task: Task, operation: string) {
  await action(async () => {
    const next = await post<Task>(`/tasks/${task.id}/${operation}`);
    if (operation === "retry" && next.kind === "analyze") {
      navigate("download");
      analysis.value = null;
      analyzingId.value = next.id;
    } else if (operation === "retry" && next.kind === "inspect") {
      navigate("convert");
      inspectingId.value = next.id;
    }
    await refresh();
  });
}
async function inspectTask(task: Task) {
  if (task.kind === "analyze") {
    navigate("download");
    useAnalysis(task);
  } else
    await action(async () => {
      await loadAsset(task.result!.asset_id!);
      navigate("convert");
    });
}
onMounted(async () => {
  window.addEventListener("hashchange", syncHash);
  await refresh();
  try {
    server.value = await api<ServerSettings>("/settings");
  } catch {
    connected.value = false;
  }
  timer = setInterval(refresh, 1500);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
  window.removeEventListener("hashchange", syncHash);
});
</script>
<template>
  <a class="skip-link" href="#main">Skip to content</a>
  <header>
    <div class="header-inner">
      <a class="brand" href="#download" @click.prevent="navigate('download')"
        ><span class="brand-icon"><Icon name="download" :size="23" /></span
        ><span>Download<span class="brand-plus"> & </span>Convert</span></a
      >
      <nav aria-label="Main navigation">
        <button
          v-for="item in tabs"
          :key="item"
          :aria-label="item"
          :aria-current="tab === item ? 'page' : undefined"
          :class="['nav-item', { selected: tab === item }]"
          @click="navigate(item)"
        >
          <Icon :name="item" :size="17" /><span>{{ item }}</span
          ><span v-if="item === 'tasks' && activeTasks.length" class="count">{{
            activeTasks.length
          }}</span>
        </button>
      </nav>
      <span class="connection"
        ><i :class="{ online: connected && worker }" />{{
          connected
            ? worker
              ? "Worker online"
              : "Worker offline"
            : "Reconnecting"
        }}</span
      >
    </div>
  </header>
  <main id="main" tabindex="-1">
    <div v-if="error" class="notice error" role="alert">
      <span><strong>Unable to continue</strong>{{ error }}</span
      ><button
        class="icon-button"
        aria-label="Dismiss error"
        @click="error = ''"
      >
        <Icon name="x" />
      </button>
    </div>
    <div v-if="feedback" class="notice success" role="status">
      <Icon name="check" /><span>{{ feedback }}</span>
    </div>
    <div v-if="connected && !worker" class="worker-notice" role="status">
      The worker is offline. Tasks will wait in the queue until it starts.
    </div>
    <template v-if="tab === 'download'">
      <div class="intro">
        <span class="eyebrow">YOUR MEDIA. YOUR WORKSPACE.</span>
        <h1>A link. A format.<br /><span>Make it yours.</span></h1>
        <p>
          Download a video or save a track.<br />Choose what you need. Keep the
          quality you picked.
        </p>
      </div>
      <section class="workspace" aria-label="Download media">
        <div class="panel-heading">
          <span class="step">01</span>
          <h2>Start with a link</h2>
          <span class="badge">Video & audio</span>
        </div>
        <form class="link-form" @submit.prevent="analyze">
          <label class="sr-only" for="source-url">Media URL</label>
          <div class="url-field">
            <Icon name="link" /><input
              id="source-url"
              v-model="url"
              type="url"
              placeholder="Paste a YouTube, SoundCloud or TikTok link"
              autocomplete="url"
              required
              :disabled="!!analyzingId"
            />
          </div>
          <button class="primary" :disabled="busy || !!analyzingId">
            {{ analyzingId ? "Analyzing…" : "Analyze link"
            }}<Icon v-if="!analyzingId" name="arrow" :size="18" /><span
              v-else
              class="spinner"
            />
          </button>
        </form>
        <p class="help">
          <Icon name="clock" :size="14" />YouTube videos & Shorts, SoundCloud
          tracks and TikTok videos. One item at a time.
        </p>
        <div v-if="analyzingId" class="loading-box" role="status">
          <span class="spinner" />{{
            tasks.find((t) => t.id === analyzingId)?.state === "queued"
              ? "Waiting for the worker…"
              : "Analyzing your link…"
          }}<button
            v-if="tasks.some((t) => t.id === analyzingId)"
            class="text-button"
            @click="
              taskAction(
                tasks.find((t) => t.id === analyzingId)!,
                'cancel',
              )
            "
          >
            Cancel
          </button>
        </div>
        <template v-if="analysis"
          ><div class="divider" />
          <div class="media-preview">
            <img
              v-if="analysis.thumbnail"
              :src="analysis.thumbnail"
              alt="Source media artwork"
              referrerpolicy="no-referrer"
            />
            <div v-else class="thumbnail-placeholder">
              <Icon name="file" :size="32" />
            </div>
            <div>
              <span class="eyebrow">{{ analysis.platform }}</span>
              <h3>{{ analysis.title }}</h3>
              <p>
                {{ analysis.author || "Creator unknown" }}
                <span class="dot">·</span> {{ duration(analysis.duration) }}
              </p>
            </div>
          </div>
          <div class="format-grid">
            <label
              >Source format<select v-model="choiceId">
                <option
                  v-for="item in analysis.choices"
                  :key="item.id"
                  :value="item.id"
                >
                  {{ choiceLabel(item) }}
                </option>
              </select></label
            ><label
              >Output preset<select v-model="profile">
                <option value="original">Original · no re-encoding</option>
                <option value="mp3" :disabled="!choice?.has_audio">
                  Audio MP3 · re-encode
                </option>
              </select></label
            >
          </div>
          <div v-if="choice" class="format-summary">
            <span
              >{{ choice.size_kind === "approximate" ? "About " : ""
              }}{{ bytes(choice.size) }}</span
            ><span>{{
              profile === "mp3"
                ? "Audio encoding required"
                : choice.operation === "merge"
                  ? "Separate tracks · lossless merge"
                  : "Direct source download"
            }}</span>
          </div>
          <details class="advanced">
            <summary>Advanced · source details & encoding</summary>
            <dl v-if="choice">
              <div>
                <dt>Source format IDs</dt>
                <dd>{{ choice.source_format_ids.join(" + ") }}</dd>
              </div>
              <div>
                <dt>Source codecs</dt>
                <dd>
                  {{
                    [choice.video_codec, choice.audio_codec]
                      .filter(Boolean)
                      .join(" / ")
                  }}
                </dd>
              </div>
              <div v-if="choice.width && choice.height">
                <dt>Source dimensions</dt>
                <dd>{{ choice.width }} × {{ choice.height }}</dd>
              </div>
              <div v-if="choice.audio_bitrate">
                <dt>Source audio bitrate</dt>
                <dd>{{ choice.audio_bitrate }} kbps</dd>
              </div>
            </dl>
            <label v-if="profile === 'mp3'"
              >MP3 output bitrate<select v-model="bitrate">
                <option :value="128">128 kbps</option>
                <option :value="192">192 kbps</option>
                <option :value="320">320 kbps</option>
              </select></label
            >
            <p class="help">
              A higher output bitrate does not restore detail missing from the
              source.
            </p>
          </details>
          <button
            class="primary wide"
            :disabled="busy || !choice"
            @click="download"
          >
            <Icon name="download" :size="18" />Add download to queue
          </button>
        </template>
      </section>
      <div class="feature-strip">
        <div>
          <Icon name="tasks" /><span
            ><strong>A queue that stays</strong>Tasks survive a page
            refresh.</span
          >
        </div>
        <div>
          <Icon name="convert" /><span
            ><strong>Saved, then converted</strong>Reuse a result while it is
            available.</span
          >
        </div>
        <div>
          <Icon name="settings" /><span
            ><strong>Your own instance</strong>Files are processed on your
            server.</span
          >
        </div>
      </div>
      <p class="below-note">
        Have a file already?
        <button class="text-button" @click="navigate('convert')">
          Open the converter ↗
        </button>
      </p>
    </template>
    <template v-if="tab === 'convert'">
      <div class="page-heading">
        <span class="eyebrow">A DIFFERENT FORMAT. THE SAME IDEA.</span>
        <h1>Give your file<br /><span>a new format.</span></h1>
        <p>
          Video, audio, images and short GIFs.<br />Compatible operations appear
          after inspection.
        </p>
      </div>
      <section class="workspace" aria-label="Convert media">
        <div
          v-if="!asset"
          :class="['dropzone', { dragging }]"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop="drop"
        >
          <span class="upload-icon"><Icon name="upload" :size="32" /></span>
          <h2>
            {{ inspectingId ? "Inspecting your file…" : "Drop your file here" }}
          </h2>
          <p>
            {{
              inspectingId
                ? "Detecting contents and compatible operations."
                : "Or choose a video, audio file, image or animation."
            }}
          </p>
          <button
            class="primary"
            :disabled="busy || !!inspectingId"
            @click="fileInput?.click()"
          >
            {{ busy ? "Uploading…" : "Choose a file"
            }}<Icon name="arrow" :size="18" />
          </button>
          <p class="help">
            {{ bytes(server?.max_file_bytes || 536870912) }} per file · Files
            expire after
            {{ Math.round((server?.ttl_seconds || 86400) / 3600) }} hours
          </p>
          <span
            v-if="inspectingId"
            class="spinner"
            role="status"
            aria-label="Inspecting file"
          />
        </div>
        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          aria-label="Choose media file"
          accept="video/*,audio/*,image/jpeg,image/png,image/webp,image/gif"
          :disabled="busy || !!inspectingId"
          @change="upload(($event.target as HTMLInputElement).files)"
        />
        <template v-if="asset"
          ><div class="panel-heading">
            <span class="step"><Icon name="file" :size="19" /></span>
            <h2 class="filename">{{ asset.name }}</h2>
            <button
              class="text-button"
              @click="
                asset = null;
                if (fileInput) fileInput.value = '';
              "
            >
              Change file
            </button>
          </div>
          <div class="source-facts">
            <span>{{ bytes(asset.size) }}</span
            ><span>{{ asset.metadata.kind }}</span
            ><span v-if="asset.metadata.width"
              >{{ asset.metadata.width }} × {{ asset.metadata.height }}</span
            ><span v-if="asset.metadata.duration">{{
              duration(asset.metadata.duration)
            }}</span
            ><span v-if="asset.metadata.audio_codec">{{
              asset.metadata.audio_codec
            }}</span>
          </div>
          <label
            >What would you like to do?<select v-model="output">
              <option
                v-for="operation in asset.operations"
                :key="operation.id"
                :value="operation.id"
              >
                {{ operation.label }}
              </option>
            </select></label
          >
          <p v-if="!asset.operations.length" class="help">
            No compatible output encoder is installed. Check server diagnostics.
          </p>
          <div v-if="output === 'gif'" class="gif-options">
            <label
              >Start (seconds)<input
                v-model.number="gifStart"
                type="number"
                min="0"
                :max="asset.metadata.duration || 7200"
                step="0.1" /></label
            ><label
              >Duration (seconds)<input
                v-model.number="gifDuration"
                type="number"
                min="0.1"
                max="15"
                step="0.1" /></label
            ><label
              >Frames per second<input
                v-model.number="gifFps"
                type="number"
                min="1"
                max="24" /></label
            ><label
              >Width (pixels)<input
                v-model.number="gifWidth"
                type="number"
                min="64"
                max="720"
            /></label>
          </div>
          <p v-if="asset.metadata.kind === 'animation'" class="help">
            Animation is preserved in video/GIF outputs. Still-frame extraction
            is planned.
          </p>
          <p v-if="output === 'jpg' && asset.metadata.transparent" class="help">
            JPEG does not support transparency. Transparent areas will use a
            white background.
          </p>
          <p v-if="['mp4', 'mkv', 'mov', 'webm'].includes(output)" class="help">
            Smaller Video: H.264 CRF 25 or VP9 CRF 34. Size depends on the
            source; encoding does not improve source quality.
          </p>
          <label v-if="['mp3', 'm4a'].includes(output)" class="bitrate"
            >Output bitrate<select v-model="bitrate">
              <option :value="128">128 kbps</option>
              <option :value="192">192 kbps</option>
              <option :value="320">320 kbps</option>
            </select></label
          ><button
            class="primary wide"
            :disabled="busy || !output"
            @click="convert"
          >
            <Icon name="convert" :size="18" />Add conversion to queue
          </button>
          <p class="help">
            Source available until {{ date(asset.expires_at) }}.
          </p>
        </template>
      </section>
    </template>
    <template v-if="tab === 'tasks'">
      <div class="page-heading compact">
        <span class="eyebrow">EVERYTHING IN ONE PLACE</span>
        <h1>Your <span>tasks.</span></h1>
        <p>Downloads and conversions, from queued to ready.</p>
      </div>
      <section v-if="!tasks.length" class="empty workspace">
        <Icon name="tasks" :size="40" />
        <h2>A clear queue. A fresh start.</h2>
        <p>Your downloads and conversions will appear here.</p>
        <button class="primary" @click="navigate('download')">
          Create your first task<Icon name="arrow" :size="18" />
        </button>
      </section>
      <template v-for="(group, index) in [activeTasks, history]" :key="index"
        ><section v-if="group.length" class="task-group">
          <div class="section-heading">
            <h2>{{ index === 0 ? "In progress" : "History" }}</h2>
            <span
              >{{ group.length }}
              {{ group.length === 1 ? "task" : "tasks" }}</span
            >
          </div>
          <article v-for="task in group" :key="task.id" class="task-card">
            <div :class="['task-icon', task.state]">
              <span v-if="task.state === 'running'" class="spinner" /><Icon
                v-else
                :name="
                  task.state === 'completed'
                    ? 'check'
                    : task.state === 'failed' || task.state === 'cancelled'
                      ? 'x'
                      : 'clock'
                "
              />
            </div>
            <div class="task-body">
              <div class="task-title">
                <h3>{{ task.title }}</h3>
                <span :class="['badge', task.state]">{{ task.state }}</span>
              </div>
              <p class="task-meta">
                {{ task.kind }} <span class="dot">·</span>
                {{ date(task.created_at) }} <span class="dot">·</span>
                {{ task.operation }}
              </p>
              <div
                v-if="task.state === 'running' && task.progress !== null"
                class="progress-wrap"
              >
                <progress
                  max="100"
                  :value="task.progress"
                  :aria-label="task.operation + ' progress'"
                /><span
                  >{{ task.progress.toFixed(0) }}%<template v-if="task.speed">
                    · {{ bytes(task.speed) }}/s</template
                  ><template v-if="task.eta">
                    · {{ duration(task.eta) }} left</template
                  ></span
                >
              </div>
              <p v-if="task.error" class="task-error">
                {{ task.error.message }}
              </p>
              <details v-if="task.error" class="error-details">
                <summary>Technical details</summary>
                <code>{{ task.error.code }} · Task {{ task.id }}</code>
              </details>
              <p v-if="task.expired" class="expired">
                Result expired. Run this task again to create a new result.
              </p>
              <p
                v-else-if="task.state === 'completed' && task.expires_at"
                class="expiry"
              >
                Available until {{ date(task.expires_at) }}
              </p>
              <img
                v-if="
                  task.result?.preview && task.result.asset_id && !task.expired
                "
                class="gif-preview"
                :src="`/api/assets/${task.result.asset_id}/preview`"
                alt="Converted image preview"
              />
              <div class="task-actions">
                <button
                  v-if="active(task)"
                  class="secondary small"
                  :disabled="busy"
                  @click="taskAction(task, 'cancel')"
                >
                  Cancel</button
                ><template v-if="task.state === 'completed' && !task.expired"
                  ><button
                    v-if="task.kind === 'analyze'"
                    class="secondary small"
                    @click="inspectTask(task)"
                  >
                    View formats<Icon name="arrow" :size="14" /></button
                  ><template v-else-if="task.result?.asset_id"
                    ><a
                      v-if="task.kind !== 'inspect'"
                      class="primary small"
                      :href="`/api/assets/${task.result.asset_id}/file`"
                      ><Icon name="download" :size="15" />Download result</a
                    ><button
                      class="secondary small"
                      :disabled="busy"
                      @click="inspectTask(task)"
                    >
                      {{
                        task.kind === "inspect"
                          ? "Choose conversion"
                          : "Convert"
                      }}
                    </button></template
                  ></template
                ><button
                  v-if="
                    task.state === 'failed' ||
                    task.state === 'cancelled' ||
                    task.expired
                  "
                  class="secondary small"
                  :disabled="busy"
                  @click="taskAction(task, 'retry')"
                >
                  {{ task.kind === "download" ? "Analyze again" : "Retry" }}
                </button>
              </div>
            </div>
          </article>
        </section></template
      >
    </template>
    <template v-if="tab === 'settings'">
      <div class="page-heading compact">
        <span class="eyebrow">YOUR INSTANCE, AT A GLANCE</span>
        <h1>Workspace <span>settings.</span></h1>
        <p>Runtime diagnostics and limits configured by the owner.</p>
      </div>
      <template v-if="server"
        ><section class="workspace settings-panel">
          <div class="panel-heading">
            <span class="step"><Icon name="settings" :size="18" /></span>
            <h2>Processing & storage</h2>
          </div>
          <dl class="settings-list">
            <div>
              <dt>Maximum file size</dt>
              <dd>{{ bytes(server.max_file_bytes) }}</dd>
            </div>
            <div>
              <dt>Storage used / limit</dt>
              <dd>
                {{ bytes(server.used_bytes) }} /
                {{ bytes(server.max_storage_bytes) }}
              </dd>
            </div>
            <div>
              <dt>Result retention</dt>
              <dd>{{ server.ttl_seconds / 3600 }} hours</dd>
            </div>
            <div>
              <dt>Concurrent tasks</dt>
              <dd>{{ server.concurrency }}</dd>
            </div>
            <div>
              <dt>Task timeout</dt>
              <dd>{{ server.job_timeout_seconds / 60 }} minutes</dd>
            </div>
            <div>
              <dt>Owner cookie file</dt>
              <dd>
                {{
                  server.cookies_configured
                    ? "Configured on server"
                    : "Not configured"
                }}
              </dd>
            </div>
          </dl>
          <p class="help">
            The owner can adjust these limits in the server environment and
            restart the service.
          </p>
        </section>
        <section class="workspace settings-panel">
          <h2>Runtime diagnostics</h2>
          <dl class="settings-list versions">
            <div v-for="(version, name) in server.versions" :key="name">
              <dt>{{ name }}</dt>
              <dd>{{ version }}</dd>
            </div>
          </dl>
        </section>
        <section class="workspace settings-panel">
          <h2>Sources & rollout</h2>
          <dl class="settings-list">
            <div v-for="platform in server.platforms" :key="platform.name">
              <dt>{{ platform.name }}</dt>
              <dd>{{ platform.status }}</dd>
            </div>
          </dl>
          <p class="help">
            Access depends on the link, region, authorization and extractor. An
            extractor listing does not guarantee a successful download.
          </p>
        </section>
        <section class="workspace settings-panel">
          <h2>Processing presets</h2>
          <dl class="preset-list">
            <div v-for="preset in server.presets" :key="preset.name">
              <dt>{{ preset.name }}</dt>
              <dd>{{ preset.description }}</dd>
            </div>
          </dl>
        </section></template
      >
    </template>
  </main>
  <footer>
    <span>Download & Convert <span class="dot">/</span> by Nord_Fillin</span
    ><a
      href="https://github.com/Denofix/youtube-downloader"
      target="_blank"
      rel="noreferrer"
      >Open source ↗</a
    >
  </footer>
</template>
