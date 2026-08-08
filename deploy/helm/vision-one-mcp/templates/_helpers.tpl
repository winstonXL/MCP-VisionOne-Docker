{{- define "vision-one-mcp.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "vision-one-mcp.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "vision-one-mcp.labels" -}}
app.kubernetes.io/name: {{ include "vision-one-mcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "vision-one-mcp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vision-one-mcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Name of the Secret holding VISION_ONE_API_KEY / MCP_BEARER_TOKEN. */}}
{{- define "vision-one-mcp.secretName" -}}
{{- if .Values.secrets.existingSecretName -}}
{{ .Values.secrets.existingSecretName }}
{{- else -}}
{{ include "vision-one-mcp.fullname" . }}
{{- end -}}
{{- end -}}
