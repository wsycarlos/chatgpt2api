"use client";

import { create } from "zustand";
import { toast } from "sonner";

import {
  fetchSettingsConfig,
  syncImageStorage,
  testImageStorageConnection,
  updateSettingsConfig,
  type ImageStorageMode,
  type ImageStorageSettings,
  type SettingsConfig,
  type ThirdPartyAppsSettings,
} from "@/lib/api";

const DEFAULT_THIRD_PARTY_APPS: ThirdPartyAppsSettings = {
  infinite_canvas: {
    enabled: false,
    url: "https://canvas.best",
  },
};

function normalizeThirdPartyApps(value: unknown): ThirdPartyAppsSettings {
  const source = typeof value === "object" && value !== null ? value as Partial<ThirdPartyAppsSettings> : {};
  const canvas = typeof source.infinite_canvas === "object" && source.infinite_canvas
    ? source.infinite_canvas as Partial<ThirdPartyAppsSettings["infinite_canvas"]>
    : {};
  return {
    infinite_canvas: {
      enabled: Boolean(canvas.enabled),
      url: String(canvas.url || DEFAULT_THIRD_PARTY_APPS.infinite_canvas.url),
    },
  };
}

function normalizeConfig(config: SettingsConfig): SettingsConfig {
  const imageStorage = typeof config.image_storage === "object" && config.image_storage
    ? config.image_storage as ImageStorageSettings
    : {
      enabled: false,
      mode: "local" as ImageStorageMode,
      webdav_url: "",
      webdav_username: "",
      webdav_password: "",
      webdav_root_path: "chatgpt2api/images",
      public_base_url: "",
    };
  const imageStorageMode: ImageStorageMode = imageStorage.enabled && imageStorage.mode === "both"
    ? "both"
    : imageStorage.enabled && imageStorage.mode === "webdav"
      ? "webdav"
      : "local";
  return {
    ...config,
    image_retention_days: Number(config.image_retention_days || 30),
    image_poll_timeout_secs: Number(config.image_poll_timeout_secs || 120),
    image_account_concurrency: Number(config.image_account_concurrency || 3),
    image_settle_enabled: Boolean(config.image_settle_enabled !== false),
    image_check_before_hit_enabled: Boolean(config.image_check_before_hit_enabled !== false),
    image_settle_secs: Number(config.image_settle_secs || 2.0),
    image_timeout_retry_secs: Number(config.image_timeout_retry_secs || 30),
    image_parallel_generation: Boolean(config.image_parallel_generation),
    log_levels: Array.isArray(config.log_levels) ? config.log_levels : [],
    proxy: typeof config.proxy === "string" ? config.proxy : "",
    base_url: typeof config.base_url === "string" ? config.base_url : "",
    global_system_prompt: String(config.global_system_prompt || ""),
    sensitive_words: Array.isArray(config.sensitive_words) ? config.sensitive_words : [],
    ai_review: {
      enabled: Boolean(config.ai_review?.enabled),
      base_url: String(config.ai_review?.base_url || ""),
      api_key: String(config.ai_review?.api_key || ""),
      model: String(config.ai_review?.model || ""),
      prompt: String(config.ai_review?.prompt || ""),
    },
    image_storage: {
      enabled: Boolean(imageStorage.enabled),
      mode: imageStorageMode,
      webdav_url: String(imageStorage.webdav_url || ""),
      webdav_username: String(imageStorage.webdav_username || ""),
      webdav_password: String(imageStorage.webdav_password || ""),
      webdav_root_path: String(imageStorage.webdav_root_path || "chatgpt2api/images"),
      public_base_url: String(imageStorage.public_base_url || ""),
    },
    third_party_apps: normalizeThirdPartyApps(config.third_party_apps),
  };
}

type SettingsStore = {
  config: SettingsConfig | null;
  isLoadingConfig: boolean;
  isSavingConfig: boolean;
  isTestingImageStorage: boolean;
  isSyncingImageStorage: boolean;

  initialize: () => Promise<void>;
  loadConfig: () => Promise<void>;
  saveConfig: () => Promise<boolean>;

  setImageRetentionDays: (value: string) => void;
  setImagePollTimeoutSecs: (value: string) => void;
  setImageAccountConcurrency: (value: string) => void;
  setImageSettleEnabled: (value: boolean) => void;
  setImageCheckBeforeHitEnabled: (value: boolean) => void;
  setImageSettleSecs: (value: string) => void;
  setImageTimeoutRetrySecs: (value: string) => void;
  setLogLevel: (level: string, enabled: boolean) => void;
  setProxy: (value: string) => void;
  setBaseUrl: (value: string) => void;
  setGlobalSystemPrompt: (value: string) => void;
  setSensitiveWordsText: (value: string) => void;
  setAIReviewField: (key: "enabled" | "base_url" | "api_key" | "model" | "prompt", value: string | boolean) => void;
  setImageStorageField: (key: keyof ImageStorageSettings, value: string | boolean) => void;
  testImageStorage: () => Promise<void>;
  syncImagesToWebDAV: () => Promise<void>;
  setInfiniteCanvasField: <K extends keyof ThirdPartyAppsSettings["infinite_canvas"]>(
    key: K,
    value: ThirdPartyAppsSettings["infinite_canvas"][K],
  ) => void;
};

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  config: null,
  isLoadingConfig: true,
  isSavingConfig: false,
  isTestingImageStorage: false,
  isSyncingImageStorage: false,

  initialize: async () => {
    await get().loadConfig();
  },

  loadConfig: async () => {
    set({ isLoadingConfig: true });
    try {
      const data = await fetchSettingsConfig();
      set({ config: normalizeConfig(data.config) });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载系统配置失败");
    } finally {
      set({ isLoadingConfig: false });
    }
  },

  saveConfig: async () => {
    const { config } = get();
    if (!config) {
      return false;
    }

    set({ isSavingConfig: true });
    try {
      const data = await updateSettingsConfig({
        ...config,
        image_retention_days: Math.max(1, Number(config.image_retention_days) || 30),
        image_poll_timeout_secs: Math.max(1, Number(config.image_poll_timeout_secs) || 120),
        image_account_concurrency: Math.max(1, Number(config.image_account_concurrency) || 3),
        image_settle_enabled: Boolean(config.image_settle_enabled !== false),
        image_check_before_hit_enabled: Boolean(config.image_check_before_hit_enabled !== false),
        image_settle_secs: Math.max(0.5, Number(config.image_settle_secs) || 2.0),
        image_timeout_retry_secs: Math.max(1, Number(config.image_timeout_retry_secs) || 30),
        image_parallel_generation: Boolean(config.image_parallel_generation),
        proxy: config.proxy.trim(),
        base_url: String(config.base_url || "").trim(),
        global_system_prompt: String(config.global_system_prompt || "").trim(),
        sensitive_words: (config.sensitive_words || []).map((item) => String(item).trim()).filter(Boolean),
        ai_review: {
          enabled: Boolean(config.ai_review?.enabled),
          base_url: String(config.ai_review?.base_url || "").trim(),
          api_key: String(config.ai_review?.api_key || "").trim(),
          model: String(config.ai_review?.model || "").trim(),
          prompt: String(config.ai_review?.prompt || "").trim(),
        },
        image_storage: {
          enabled: Boolean(config.image_storage?.enabled),
          mode: config.image_storage?.enabled && ["webdav", "both"].includes(String(config.image_storage?.mode))
            ? config.image_storage.mode
            : "local",
          webdav_url: String(config.image_storage?.webdav_url || "").trim(),
          webdav_username: String(config.image_storage?.webdav_username || "").trim(),
          webdav_password: String(config.image_storage?.webdav_password || "").trim(),
          webdav_root_path: String(config.image_storage?.webdav_root_path || "chatgpt2api/images").trim(),
          public_base_url: String(config.image_storage?.public_base_url || "").trim(),
        },
        third_party_apps: {
          infinite_canvas: {
            enabled: Boolean(config.third_party_apps?.infinite_canvas?.enabled),
            url: String(config.third_party_apps?.infinite_canvas?.url || DEFAULT_THIRD_PARTY_APPS.infinite_canvas.url).trim(),
          },
        },
      });
      set({ config: normalizeConfig(data.config) });
      window.dispatchEvent(new Event("third-party-apps-updated"));
      toast.success("配置已保存");
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存系统配置失败");
      return false;
    } finally {
      set({ isSavingConfig: false });
    }
  },

  setImageRetentionDays: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_retention_days: value } } : {});
  },

  setImagePollTimeoutSecs: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_poll_timeout_secs: value } } : {});
  },

  setImageAccountConcurrency: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_account_concurrency: value } } : {});
  },

  setImageSettleEnabled: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_settle_enabled: value, image_check_before_hit_enabled: value } } : {});
  },

  setImageCheckBeforeHitEnabled: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_check_before_hit_enabled: value } } : {});
  },

  setImageSettleSecs: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_settle_secs: value } } : {});
  },

  setImageTimeoutRetrySecs: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_timeout_retry_secs: value } } : {});
  },

  setLogLevel: (level, enabled) => {
    set((state) => {
      if (!state.config) return {};
      const levels = new Set(state.config.log_levels || []);
      if (enabled) levels.add(level);
      else levels.delete(level);
      return { config: { ...state.config, log_levels: Array.from(levels) } };
    });
  },

  setProxy: (value) => {
    set((state) => state.config ? { config: { ...state.config, proxy: value } } : {});
  },

  setBaseUrl: (value) => {
    set((state) => state.config ? { config: { ...state.config, base_url: value } } : {});
  },

  setGlobalSystemPrompt: (value) => {
    set((state) => state.config ? { config: { ...state.config, global_system_prompt: value } } : {});
  },

  setSensitiveWordsText: (value) => {
    set((state) => state.config ? { config: { ...state.config, sensitive_words: value.split("\n") } } : {});
  },

  setAIReviewField: (key, value) => {
    set((state) => state.config ? { config: { ...state.config, ai_review: { ...(state.config.ai_review || {}), [key]: value } } } : {});
  },

  setImageStorageField: (key, value) => {
    set((state) => {
      if (!state.config?.image_storage) {
        return {};
      }
      const next = {
        ...state.config.image_storage,
        [key]: value,
      };
      if (key === "enabled" && !value) {
        next.mode = "local";
      }
      if (key === "enabled" && value && next.mode === "local") {
        next.mode = "webdav";
      }
      return {
        config: {
          ...state.config,
          image_storage: next,
        },
      };
    });
  },

  testImageStorage: async () => {
    set({ isTestingImageStorage: true });
    try {
      const saved = await get().saveConfig();
      if (!saved) {
        return;
      }
      const data = await testImageStorageConnection();
      if (data.result.ok) {
        toast.success(`WebDAV 连接可用：HTTP ${data.result.status}`);
      } else {
        toast.error(`WebDAV 连接失败：${data.result.error ?? `HTTP ${data.result.status}`}`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "测试 WebDAV 失败");
    } finally {
      set({ isTestingImageStorage: false });
    }
  },

  syncImagesToWebDAV: async () => {
    set({ isSyncingImageStorage: true });
    try {
      const saved = await get().saveConfig();
      if (!saved) {
        return;
      }
      const data = await syncImageStorage();
      toast.success(`同步完成：上传 ${data.result.uploaded}，跳过 ${data.result.skipped}，失败 ${data.result.failed}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "同步图片失败");
    } finally {
      set({ isSyncingImageStorage: false });
    }
  },

  setInfiniteCanvasField: (key, value) => {
    set((state) => {
      if (!state.config) {
        return {};
      }
      const apps = normalizeThirdPartyApps(state.config.third_party_apps);
      return {
        config: {
          ...state.config,
          third_party_apps: {
            ...apps,
            infinite_canvas: {
              ...apps.infinite_canvas,
              [key]: value,
            },
          },
        },
      };
    });
  },
}));
