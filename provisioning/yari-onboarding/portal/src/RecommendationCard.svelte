<script lang="ts">
  import type { AnyRecord } from './types';

  export let item: AnyRecord;
  export let app: AnyRecord;
  export let registryApp: AnyRecord | undefined = undefined;
  export let statusLabel = 'Recommended';
  export let statusClass = '';
  export let registryActionLabel = (_app: AnyRecord) => 'Install manifest';
  export let onOpen = (_path: string) => {};
  export let onInstall = (_appId: string) => {};
</script>

<article class="app-card">
  <div class="app-card-title">
    <div>
      <strong>{app.name || item.name || item.id}</strong>
      <small>{item.id}</small>
    </div>
    <span class={`status-pill ${statusClass}`}>{statusLabel}</span>
  </div>
  <p>{item.reason}</p>
  <dl class="meta-list compact-meta">
    <div><dt>Next</dt><dd>{item.action?.label || statusLabel}</dd></div>
    {#if item.action?.reason}<div><dt>Reason</dt><dd>{item.action.reason}</dd></div>{/if}
  </dl>
  <div class="row compact">
    {#if app.ui?.path}<button class="secondary" type="button" on:click={() => onOpen(app.ui.path)}>Open UI</button>{/if}
    {#if registryApp && !app.installed}<button class="secondary" type="button" disabled={!registryApp.actions?.apply} title={registryApp.actions?.reason || ''} on:click={() => onInstall(registryApp.id)}>{registryActionLabel(registryApp)}</button>{/if}
    {#if registryApp && app.installed && registryApp.actions?.update}<button class="secondary" type="button" on:click={() => onInstall(registryApp.id)}>Apply update</button>{/if}
  </div>
</article>
