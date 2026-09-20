#!/usr/bin/env bash
# 服务器一键更新料盒字典：备份库存 → 拉最新代码 → 重建容器。
# 不会覆盖 .env，也不会清空 data/（物料在 data/parts.db）。
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/parts-dict}"
REPO="${REPO:-git@github.com:123XH-sudo/parts-dict.git}"
BRANCH="${BRANCH:-main}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/parts-dict-backups}"
KEEP_BACKUPS="${KEEP_BACKUPS:-10}"

log() { printf '[update] %s\n' "$*"; }
die() { printf '[update] 错误: %s\n' "$*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "找不到命令: $1"
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "需要 docker compose 或 docker-compose"
  fi
}

prune_backups() {
  local prefix="$1"
  local i=0
  local path
  shopt -s nullglob
  local items=("$BACKUP_ROOT"/"$prefix"-*)
  shopt -u nullglob
  if [ "${#items[@]}" -eq 0 ]; then
    return 0
  fi
  # 按时间新→旧
  while IFS= read -r path; do
    i=$((i + 1))
    if [ "$i" -gt "$KEEP_BACKUPS" ]; then
      rm -rf "$path"
    fi
  done < <(ls -1dt "${items[@]}")
}

backup() {
  mkdir -p "$BACKUP_ROOT"
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  if [ -d "$APP_DIR/data" ]; then
    cp -a "$APP_DIR/data" "$BACKUP_ROOT/data-$ts"
    log "已备份库存 → $BACKUP_ROOT/data-$ts"
  else
    log "没有 $APP_DIR/data，跳过库存备份"
  fi
  if [ -f "$APP_DIR/.env" ]; then
    cp -a "$APP_DIR/.env" "$BACKUP_ROOT/env-$ts"
    log "已备份配置 → $BACKUP_ROOT/env-$ts"
  fi
  prune_backups data
  prune_backups env
}

stop_app() {
  if [ -f "$APP_DIR/docker-compose.yml" ]; then
    log "停止旧容器"
    (cd "$APP_DIR" && compose down) || true
  fi
}

sync_from_git() {
  mkdir -p "$APP_DIR"
  if [ -d "$APP_DIR/.git" ]; then
    log "拉取 $BRANCH"
    if git -C "$APP_DIR" remote get-url origin >/dev/null 2>&1; then
      git -C "$APP_DIR" remote set-url origin "$REPO"
    else
      git -C "$APP_DIR" remote add origin "$REPO"
    fi
    git -C "$APP_DIR" fetch origin "$BRANCH"
    git -C "$APP_DIR" checkout -f -B "$BRANCH" "origin/$BRANCH"
    git -C "$APP_DIR" reset --hard "origin/$BRANCH"
    return 0
  fi

  local tmp
  tmp="$(mktemp -d /tmp/parts-dict-src.XXXXXX)"
  trap 'rm -rf "$tmp"' RETURN
  log "克隆 $REPO ($BRANCH)"
  git clone --branch "$BRANCH" --depth 1 "$REPO" "$tmp/src"

  if [ -f "$APP_DIR/docker-compose.yml" ] || [ -d "$APP_DIR/data" ] || [ -f "$APP_DIR/.env" ]; then
    log "当前目录还不是 git 仓库，保留 data/ 和 .env，换上新代码"
    local saved="$tmp/keep"
    mkdir -p "$saved"
    [ -d "$APP_DIR/data" ] && mv "$APP_DIR/data" "$saved/data"
    [ -f "$APP_DIR/.env" ] && mv "$APP_DIR/.env" "$saved/.env"
    rm -rf "$APP_DIR"
    mv "$tmp/src" "$APP_DIR"
    [ -d "$saved/data" ] && mv "$saved/data" "$APP_DIR/data"
    [ -f "$saved/.env" ] && mv "$saved/.env" "$APP_DIR/.env"
  else
    rm -rf "$APP_DIR"
    mv "$tmp/src" "$APP_DIR"
  fi
}

need git
need docker
need mktemp

log "目录 $APP_DIR"
backup
stop_app
sync_from_git
trap - RETURN

mkdir -p "$APP_DIR/data"
if [ ! -f "$APP_DIR/.env" ]; then
  die "没有 $APP_DIR/.env。从备份拷回后再运行：cp $BACKUP_ROOT/env-最新 $APP_DIR/.env"
fi
if [ ! -f "$APP_DIR/data/parts.db" ]; then
  log "警告: 还没有 data/parts.db。若这是老站点，先把备份拷回来再启动。"
fi

log "重建并启动"
(cd "$APP_DIR" && compose up -d --build)
(cd "$APP_DIR" && compose ps)
log "完成。库存: $APP_DIR/data  备份: $BACKUP_ROOT"
log "以后在这台机器上执行: $APP_DIR/scripts/update.sh"
