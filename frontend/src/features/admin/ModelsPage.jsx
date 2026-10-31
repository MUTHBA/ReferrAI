// -----------------------------------------------------------------------------
// AI models: the three trained models (referral quality, fraud risk, churn
// risk) with when they were trained, on how much data, accuracy on held-out
// data (ROC AUC) and the inputs they use. Admins can retrain (runs in the
// background; scoring keeps using the current models meanwhile) or run the
// churn and ranking scoring now instead of waiting for the daily run.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { PageHeader } from '@/components/app/PageHeader'
import { ErrorState, LoadingRows } from '@/components/app/States'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { Pill } from '@/components/ui/pill'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { adminApi } from '@/lib/endpoints'
import { dateTime, number } from '@/lib/format'

const MODELS = {
  quality: { title: 'Referral quality', about: 'How likely a sale is to be a genuine, lasting customer. Scored for every sale.' },
  fraud: { title: 'Fraud risk', about: 'Unusual click patterns (anomaly detection), plus fixed rules. Scored for every click.' },
  churn: { title: 'Churn risk', about: 'How likely a partner is to stop referring in the next 30 days. Scored daily.' },
}

function auc(model) {
  const v = model.metrics?.holdout?.roc_auc
  return v === undefined || v === null ? '—' : Number(v).toFixed(2)
}

function ModelCard({ model }) {
  const info = MODELS[model.name] || { title: model.name }
  return (
    <Panel className="flex flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h2 className="text-section font-semibold text-ink">{info.title}</h2>
          <p className="mt-0.5 text-caption text-muted-text">{info.about}</p>
        </div>
        {model.trained ? <Pill tone="jade" dot>Trained</Pill> : <Pill tone="amber" dot>Not trained</Pill>}
      </div>
      {model.trained ? (
        <div className="flex flex-1 flex-col px-5 py-4">
          <dl className="divide-y divide-line text-caption">
            <div className="flex justify-between gap-3 py-2">
              <dt className="text-muted-text">Trained on</dt>
              <dd className="font-medium">{dateTime(model.trained_at)}</dd>
            </div>
            <div className="flex justify-between gap-3 py-2">
              <dt className="text-muted-text">Training data</dt>
              <dd className="font-medium">{number(model.training_rows)} synthetic examples</dd>
            </div>
            <div className="flex justify-between gap-3 py-2">
              <dt className="text-muted-text" title="Area under the ROC curve on partners held out of training. 0.5 = guessing, 1.0 = perfect.">
                Accuracy (ROC AUC)
              </dt>
              <dd className="tabular text-body font-semibold text-ink">{auc(model)}</dd>
            </div>
          </dl>
          <div className="mt-4 text-label font-medium text-muted-text">Inputs</div>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {(model.feature_labels || model.features || []).map((f) => (
              <li key={f} className="rounded-[6px] border border-line bg-canvas px-2 py-1 text-label text-text">
                {f}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="px-5 py-4 text-caption text-muted-text">
          Until it&apos;s trained, these scores show as &ldquo;Not trained yet&rdquo;
          {model.name === 'fraud' ? ' and fraud checks use the fixed rules only' : ''}. Click Retrain models.
        </p>
      )}
    </Panel>
  )
}

export default function ModelsPage() {
  const qc = useQueryClient()
  const [confirm, setConfirm] = useState(false)
  const status = useQuery({
    queryKey: ['ai-models'],
    queryFn: adminApi.models,
    refetchInterval: (q) => (q.state.data?.state === 'running' ? 3000 : false),
  })
  const scoring = useMutation({
    mutationFn: async () => {
      const churn = await adminApi.runChurn()
      const rank = await adminApi.runRanking()
      return { churn, rank }
    },
    onSuccess: ({ churn }) => {
      toast.success(`Scored ${number(churn.partners_scored)} partners for churn and ranking.`)
      for (const key of ['partners', 'admin-dashboard', 'partner-scores', 'score']) qc.invalidateQueries({ queryKey: [key] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const s = status.data
  const running = s?.state === 'running'

  async function retrain() {
    await adminApi.train(['quality', 'fraud', 'churn'])
    toast.success('Training started. This page updates when it finishes.')
    qc.invalidateQueries({ queryKey: ['ai-models'] })
  }

  return (
    <>
      <PageHeader
        title="AI models"
        description="Scores refresh automatically. Models are trained on synthetic data and checked on partners they never saw."
        actions={
          <>
            <Button variant="secondary" onClick={() => scoring.mutate()} disabled={scoring.isPending}>
              {scoring.isPending ? <Spinner /> : <Play />}
              Run scoring now
            </Button>
            <Button onClick={() => setConfirm(true)} disabled={running}>
              {running ? <Spinner /> : <RefreshCw />}
              {running ? 'Training…' : 'Retrain models'}
            </Button>
          </>
        }
      />
      {running && (
        <Alert variant="info" className="mb-6">
          Training {s.models.join(', ')} since {dateTime(s.started_at)}. Scoring keeps using the current models until it finishes.
        </Alert>
      )}
      {s?.state === 'failed' && (
        <Alert variant="error" className="mb-6">
          The last training run failed: {s.error}
        </Alert>
      )}
      {s?.state === 'succeeded' && s.finished_at && (
        <Alert variant="success" className="mb-6">
          Last training run finished {dateTime(s.finished_at)}.
        </Alert>
      )}
      {status.isLoading ? (
        <Panel>
          <LoadingRows rows={6} />
        </Panel>
      ) : status.isError ? (
        <Panel>
          <ErrorState error={status.error} onRetry={status.refetch} />
        </Panel>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          {s.available_models.map((m) => (
            <ModelCard key={m.name} model={m} />
          ))}
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Retrain all models?"
        description="Takes about a minute. Scoring keeps working with the current models until the new ones are ready."
        confirmLabel="Retrain models"
        onConfirm={retrain}
      />
    </>
  )
}
