"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Copy, ExternalLink, LoaderCircle, RefreshCw, Star, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  createAccounts,
  deleteAccounts,
  fetchAccounts,
  finishOAuthLogin,
  setDefaultAccount,
  startOAuthLogin,
  type Account,
  type OAuthLoginStartResponse,
} from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";
import { cn } from "@/lib/utils";

function maskToken(token?: string | null) {
  if (!token) return "—";
  if (token.length <= 18) return token;
  return `${token.slice(0, 16)}...${token.slice(-8)}`;
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function splitTokens(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function useAccounts() {
  const didLoadRef = useRef(false);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const data = await fetchAccounts();
      setAccounts(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载账户失败");
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  useEffect(() => {
    if (didLoadRef.current) return;
    didLoadRef.current = true;
    void load();
  }, []);

  return { accounts, setAccounts, isLoading, load };
}

function OAuthDialog({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (items: Account[]) => void;
}) {
  const [emailHint, setEmailHint] = useState("");
  const [session, setSession] = useState<OAuthLoginStartResponse | null>(null);
  const [callback, setCallback] = useState("");
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setEmailHint("");
    setSession(null);
    setCallback("");
    setStarting(false);
    setSubmitting(false);
  };

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next);
    if (!next) {
      reset();
    }
  };

  const handleStart = async () => {
    setStarting(true);
    try {
      const data = await startOAuthLogin(emailHint.trim());
      setSession(data);
      setCallback("");
      if (typeof window !== "undefined") {
        window.open(data.authorize_url, "_blank", "noopener,noreferrer");
      }
      toast.success("已打开 OpenAI 授权页面，请登录后复制 callback URL 回来");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "OAuth 起始失败");
    } finally {
      setStarting(false);
    }
  };

  const handleCopyUrl = async () => {
    if (!session) return;
    try {
      await navigator.clipboard.writeText(session.authorize_url);
      toast.success("授权 URL 已复制");
    } catch {
      toast.error("复制失败，请手动复制");
    }
  };

  const handleFinish = async () => {
    if (!session) {
      toast.error("请先获取授权链接");
      return;
    }
    const trimmed = callback.trim();
    if (!trimmed) {
      toast.error("请粘贴 callback URL 或 code");
      return;
    }
    setSubmitting(true);
    try {
      const data = await finishOAuthLogin(session.session_id, trimmed);
      onImported(data.items);
      handleOpenChange(false);
      toast.success(`OAuth 登录完成，新增 ${data.added ?? 0} 个，跳过 ${data.skipped ?? 0} 个重复项`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "OAuth 登录失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent showCloseButton={false} className="rounded-2xl p-6">
        <DialogHeader className="gap-2">
          <DialogTitle>添加 ChatGPT 账号</DialogTitle>
          <DialogDescription className="text-sm leading-6">
            通过 OpenAI OAuth 登录已有账号，系统会自动保存 refresh_token 并在后台续期。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm leading-6 text-stone-600 space-y-1">
            <div className="font-medium text-stone-800">操作步骤</div>
            <ol className="list-decimal pl-5 space-y-1">
              <li>（可选）填写 ChatGPT 账号邮箱，登录页会预填。</li>
              <li>点击“打开授权页面”，在新标签页登录。</li>
              <li>登录完成后复制地址栏的 callback URL。</li>
              <li>把 callback URL 粘到下方，点击“完成添加”。</li>
            </ol>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">邮箱（可选预填）</label>
            <Input
              type="email"
              placeholder="you@example.com"
              value={emailHint}
              onChange={(event) => setEmailHint(event.target.value)}
              disabled={Boolean(session) || starting}
              className="h-11 rounded-xl border-stone-200 bg-white"
            />
          </div>
          {!session ? (
            <Button
              type="button"
              className="h-10 rounded-xl bg-stone-950 text-white hover:bg-stone-800"
              onClick={() => void handleStart()}
              disabled={starting}
            >
              {starting ? <LoaderCircle className="size-4 animate-spin" /> : <ExternalLink className="size-4" />}
              打开授权页面
            </Button>
          ) : (
            <div className="space-y-3">
              <div className="rounded-2xl border border-stone-200 bg-white p-3 text-xs leading-6 text-stone-600 break-all font-mono">
                {session.authorize_url}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" className="rounded-xl border-stone-200 bg-white" onClick={() => void handleCopyUrl()}>
                  <Copy className="size-4" />
                  复制授权 URL
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-xl border-stone-200 bg-white"
                  onClick={() => window.open(session.authorize_url, "_blank", "noopener,noreferrer")}
                >
                  <ExternalLink className="size-4" />
                  再次打开
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-xl border-stone-200 bg-white"
                  onClick={() => {
                    setSession(null);
                    setCallback("");
                  }}
                >
                  重新生成
                </Button>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-stone-700">粘贴 callback URL（或仅 code）</label>
                <Textarea
                  placeholder="https://platform.openai.com/auth/callback?code=...&state=..."
                  value={callback}
                  onChange={(event) => setCallback(event.target.value)}
                  className="min-h-24 resize-none rounded-xl border-stone-200 font-mono text-xs"
                />
              </div>
            </div>
          )}
        </div>
        <DialogFooter className="pt-2">
          <Button
            variant="secondary"
            className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200"
            onClick={() => handleOpenChange(false)}
            disabled={submitting}
          >
            取消
          </Button>
          <Button
            className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
            onClick={() => void handleFinish()}
            disabled={!session || !callback.trim() || submitting}
          >
            {submitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
            完成添加
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ImportTokenDialog({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (items: Account[]) => void;
}) {
  const [tokens, setTokens] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setTokens("");
    setSubmitting(false);
  };

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next);
    if (!next) reset();
  };

  const handleSubmit = async () => {
    const normalized = splitTokens(tokens);
    if (normalized.length === 0) {
      toast.error("请先粘贴至少一个 Access Token");
      return;
    }
    setSubmitting(true);
    try {
      const data = await createAccounts(normalized);
      onImported(data.items);
      handleOpenChange(false);
      toast.success(`导入完成，新增 ${data.added ?? 0} 个，跳过 ${data.skipped ?? 0} 个重复项`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入失败");
    } finally {
      setSubmitting(false);
    }
  };

  const count = useMemo(() => splitTokens(tokens).length, [tokens]);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent showCloseButton={false} className="rounded-2xl p-6">
        <DialogHeader className="gap-2">
          <DialogTitle>导入 Access Token</DialogTitle>
          <DialogDescription className="text-sm leading-6">
            每行一个 Access Token，系统会自动识别邮箱信息。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <Textarea
            placeholder="每行一个 Access Token..."
            value={tokens}
            onChange={(event) => setTokens(event.target.value)}
            className="min-h-56 resize-none rounded-xl border-stone-200 font-mono text-xs"
          />
          <div className="text-xs text-stone-400">当前识别 {count} 个 Token</div>
        </div>
        <DialogFooter className="pt-2">
          <Button
            variant="secondary"
            className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200"
            onClick={() => handleOpenChange(false)}
            disabled={submitting}
          >
            取消
          </Button>
          <Button
            className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
            onClick={() => void handleSubmit()}
            disabled={submitting}
          >
            {submitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
            导入
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AccountsPageContent() {
  const { accounts, setAccounts, isLoading, load } = useAccounts();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [defaultPendingId, setDefaultPendingId] = useState<string | null>(null);
  const [oauthOpen, setOauthOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      const data = await deleteAccounts([id]);
      setAccounts(data.items);
      toast.success(`已删除账户`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除账户失败");
    } finally {
      setDeletingId(null);
    }
  };

  const handleSetDefault = async (id: string) => {
    setDefaultPendingId(id);
    try {
      const data = await setDefaultAccount(id);
      setAccounts(data.items);
      toast.success("已设为默认账号");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "设置默认账号失败");
    } finally {
      setDefaultPendingId(null);
    }
  };

  const handleCopy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success("Token 已复制");
    } catch {
      toast.error("复制失败");
    }
  };

  return (
    <>
      <section className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Personal Account</div>
          <h1 className="text-2xl font-semibold tracking-tight">账号管理</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            className="h-10 rounded-xl border-stone-200 bg-white/80 px-4 text-stone-700 hover:bg-white"
            onClick={() => void load()}
            disabled={isLoading}
          >
            <RefreshCw className={cn("size-4", isLoading ? "animate-spin" : "")} />
            刷新
          </Button>
          <Button
            className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800"
            onClick={() => setOauthOpen(true)}
          >
            <ExternalLink className="size-4" />
            添加 ChatGPT 账号
          </Button>
          <Button
            variant="outline"
            className="h-10 rounded-xl border-stone-200 bg-white/80 px-4 text-stone-700 hover:bg-white"
            onClick={() => setImportOpen(true)}
          >
            <Upload className="size-4" />
            导入 Token
          </Button>
        </div>
      </section>

      <section className="space-y-4">
        {isLoading && accounts.length === 0 ? (
          <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
            <CardContent className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
              <div className="rounded-xl bg-stone-100 p-3 text-stone-500">
                <LoaderCircle className="size-5 animate-spin" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-stone-700">正在加载账户</p>
                <p className="text-sm text-stone-500">从后端同步账号列表。</p>
              </div>
            </CardContent>
          </Card>
        ) : accounts.length === 0 ? (
          <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
            <CardContent className="px-6 py-14 text-center text-sm text-stone-500">
              暂无账号。点击上方按钮通过 OAuth 登录或导入 Access Token。
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {accounts.map((account) => (
              <Card key={account.id} className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
                <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-semibold text-stone-900">{account.email ?? "未识别邮箱"}</span>
                      {account.is_default ? (
                        <Badge variant="success" className="rounded-md">
                          <CheckCircle2 className="mr-1 size-3" />
                          默认
                        </Badge>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-stone-600">
                      <span className="font-mono">{maskToken(account.access_token)}</span>
                      <button
                        type="button"
                        className="rounded-lg p-1 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700"
                        onClick={() => void handleCopy(account.access_token)}
                      >
                        <Copy className="size-4" />
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500">
                      <span>创建时间 {formatDateTime(account.created_at)}</span>
                      <span>更新时间 {formatDateTime(account.updated_at)}</span>
                      {account.last_refresh_error ? (
                        <span className="text-rose-500">刷新异常：{account.last_refresh_error}</span>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!account.is_default ? (
                      <Button
                        variant="outline"
                        className="h-9 rounded-xl border-stone-200 bg-white px-4 text-stone-700 hover:bg-stone-50"
                        onClick={() => void handleSetDefault(account.id)}
                        disabled={defaultPendingId === account.id}
                      >
                        {defaultPendingId === account.id ? (
                          <LoaderCircle className="size-4 animate-spin" />
                        ) : (
                          <Star className="size-4" />
                        )}
                        设为默认
                      </Button>
                    ) : null}
                    <Button
                      variant="outline"
                      className="h-9 rounded-xl border-rose-200 bg-white px-4 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                      onClick={() => void handleDelete(account.id)}
                      disabled={deletingId === account.id}
                    >
                      {deletingId === account.id ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                      删除
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <OAuthDialog open={oauthOpen} onOpenChange={setOauthOpen} onImported={(items) => setAccounts(items)} />
      <ImportTokenDialog open={importOpen} onOpenChange={setImportOpen} onImported={(items) => setAccounts(items)} />
    </>
  );
}

export default function AccountsPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);

  if (isCheckingAuth || !session || session.role !== "admin") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return <AccountsPageContent />;
}
