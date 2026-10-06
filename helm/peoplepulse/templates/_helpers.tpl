{{/* Common labels */}}
{{- define "peoplepulse.labels" -}}
app.kubernetes.io/part-of: peoplepulse
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "peoplepulse.dbHost" -}}
{{- if eq .Values.database.mode "internal" -}}
{{ .Release.Name }}-postgres
{{- else -}}
{{ required "database.host is required when database.mode=external" .Values.database.host }}
{{- end -}}
{{- end -}}
