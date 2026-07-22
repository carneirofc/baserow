{{/* Chart name */}}
{{- define "baserow.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully qualified app name */}}
{{- define "baserow.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "baserow.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Common labels */}}
{{- define "baserow.labels" -}}
helm.sh/chart: {{ include "baserow.chart" . }}
{{ include "baserow.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: baserow
{{- end -}}

{{/* Selector labels */}}
{{- define "baserow.selectorLabels" -}}
app.kubernetes.io/name: {{ include "baserow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Per-component selector labels */}}
{{- define "baserow.componentSelectorLabels" -}}
{{ include "baserow.selectorLabels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "baserow.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "baserow.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Chart-managed Secret name (for SECRET_KEY, external creds, S3, etc.) */}}
{{- define "baserow.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- include "baserow.fullname" . -}}
{{- end -}}
{{- end -}}

{{/* Image references */}}
{{- define "baserow.image.backend" -}}
{{- $tag := default .Chart.AppVersion .Values.image.backend.tag -}}
{{- printf "%s/%s:%s" .Values.image.registry .Values.image.backend.repository $tag -}}
{{- end -}}

{{- define "baserow.image.webFrontend" -}}
{{- $tag := default .Chart.AppVersion .Values.image.webFrontend.tag -}}
{{- printf "%s/%s:%s" .Values.image.registry .Values.image.webFrontend.repository $tag -}}
{{- end -}}

{{/* ---- Database connection selection ---- */}}
{{- define "baserow.database.host" -}}
{{- if .Values.postgresql.enabled -}}
{{- printf "%s-postgresql" .Release.Name -}}
{{- else -}}
{{- required "externalDatabase.host is required when postgresql.enabled=false" .Values.externalDatabase.host -}}
{{- end -}}
{{- end -}}

{{- define "baserow.database.port" -}}
{{- if .Values.postgresql.enabled -}}5432{{- else -}}{{- .Values.externalDatabase.port | default 5432 -}}{{- end -}}
{{- end -}}

{{- define "baserow.database.user" -}}
{{- if .Values.postgresql.enabled -}}{{- .Values.postgresql.auth.username -}}{{- else -}}{{- .Values.externalDatabase.user -}}{{- end -}}
{{- end -}}

{{- define "baserow.database.name" -}}
{{- if .Values.postgresql.enabled -}}{{- .Values.postgresql.auth.database -}}{{- else -}}{{- .Values.externalDatabase.database -}}{{- end -}}
{{- end -}}

{{/* Secret holding DATABASE_PASSWORD, and its key */}}
{{- define "baserow.database.secretName" -}}
{{- if .Values.postgresql.enabled -}}
{{- printf "%s-postgresql" .Release.Name -}}
{{- else if .Values.externalDatabase.existingSecret -}}
{{- .Values.externalDatabase.existingSecret -}}
{{- else -}}
{{- include "baserow.secretName" . -}}
{{- end -}}
{{- end -}}

{{- define "baserow.database.secretKey" -}}
{{- if .Values.postgresql.enabled -}}
password
{{- else if .Values.externalDatabase.existingSecret -}}
{{- .Values.externalDatabase.existingSecretPasswordKey -}}
{{- else -}}
database-password
{{- end -}}
{{- end -}}

{{/* ---- Redis connection selection ---- */}}
{{- define "baserow.redis.host" -}}
{{- if .Values.redis.enabled -}}
{{- printf "%s-redis-master" .Release.Name -}}
{{- else -}}
{{- required "externalRedis.host is required when redis.enabled=false" .Values.externalRedis.host -}}
{{- end -}}
{{- end -}}

{{- define "baserow.redis.port" -}}
{{- if .Values.redis.enabled -}}6379{{- else -}}{{- .Values.externalRedis.port | default 6379 -}}{{- end -}}
{{- end -}}

{{- define "baserow.redis.secretName" -}}
{{- if .Values.redis.enabled -}}
{{- printf "%s-redis" .Release.Name -}}
{{- else if .Values.externalRedis.existingSecret -}}
{{- .Values.externalRedis.existingSecret -}}
{{- else -}}
{{- include "baserow.secretName" . -}}
{{- end -}}
{{- end -}}

{{- define "baserow.redis.secretKey" -}}
{{- if .Values.redis.enabled -}}
redis-password
{{- else if .Values.externalRedis.existingSecret -}}
{{- .Values.externalRedis.existingSecretPasswordKey -}}
{{- else -}}
redis-password
{{- end -}}
{{- end -}}

{{/* S3 credential secret name */}}
{{- define "baserow.s3.secretName" -}}
{{- if .Values.objectStorage.existingSecret -}}
{{- .Values.objectStorage.existingSecret -}}
{{- else -}}
{{- include "baserow.secretName" . -}}
{{- end -}}
{{- end -}}

{{/* Shared non-secret env (all app pods) */}}
{{- define "baserow.envFrom" -}}
- configMapRef:
    name: {{ include "baserow.fullname" . }}-env
{{- end -}}

{{/* Secret-backed env vars, mapping Secret keys to Baserow env names */}}
{{- define "baserow.secretEnv" -}}
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "baserow.secretName" . }}
      key: secret-key
- name: BASEROW_JWT_SIGNING_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "baserow.secretName" . }}
      key: jwt-signing-key
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "baserow.database.secretName" . }}
      key: {{ include "baserow.database.secretKey" . }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "baserow.redis.secretName" . }}
      key: {{ include "baserow.redis.secretKey" . }}
{{- if .Values.objectStorage.enabled }}
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "baserow.s3.secretName" . }}
      key: s3-access-key-id
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "baserow.s3.secretName" . }}
      key: s3-secret-access-key
{{- end }}
{{- end -}}

{{/* Writable-tmpfs volumes required by readOnlyRootFilesystem */}}
{{- define "baserow.tmpVolumes" -}}
- name: tmp
  emptyDir: {}
- name: dshm
  emptyDir:
    medium: Memory
{{- end -}}

{{- define "baserow.tmpVolumeMounts" -}}
- name: tmp
  mountPath: /tmp
- name: dshm
  mountPath: /dev/shm
{{- end -}}
