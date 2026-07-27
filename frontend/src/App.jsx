import { useEffect, useState, useRef, useCallback } from "react";
import ErrorBoundary from './ErrorBoundary.jsx';
import CmEditor from './CmEditor.jsx';
import {
  analyzeChartWithImage,
  analyzeStructure,
  extractDeplot,
  generateSampleEssay,
  generateSpatialSampleEssay,
  getAuthConfig,
  getCurrentUser,
  login as loginUser,
  logout as logoutUser,
  prepareTaskImage,
  requestNextSentence,
  resolveBackendUrl,
  reviewRevision,
  saveFinalImage,
  saveRevisionText,
} from "./api";
import Login from "./Login";
import {
  ArrowRight,
  BarChart3,
  FileText,
  GitBranch,
  LogOut,
  RotateCcw,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import "./App.css";
import Flowchart from "./Flowchart";//对应修改1

import {
  analysisRequirement,
  KNOWN_TASK_TYPES,
  sampleEssayRequirement,
  SPATIAL_TASK_TYPES,
  STATISTICAL_TASK_TYPES,
  taskTypeLabel,
} from './utils/taskTypes';

function formatFeedbackNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '';
  return Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, '');
}

function ChartFeedbackDetails({ chartData }) {
  if (!['pie', 'bar', 'line'].includes(chartData?.chart_type)) return null;
  const isPie = chartData.chart_type === 'pie';
  const comparison = chartData.comparison || {};
  const issues = Array.isArray(comparison.incorrect_official_items)
    ? comparison.incorrect_official_items.filter(Boolean)
    : [];
  const recordIssues = Array.isArray(chartData.records)
    ? chartData.records.filter((record) => ['incorrect', 'conflicting', 'missing', 'unexpected'].includes(record?.feedback_status))
    : [];
  const total = Number(comparison.student_percentage_total);
  const expectedTotal = Number(comparison.expected_percentage_total);
  const difference = Number(comparison.percentage_difference);
  const balance = comparison.percentage_balance;
  const hasTotal = isPie && Number.isFinite(total);
  const hasBalanceIssue = isPie && (balance === 'under' || balance === 'over');
  const unitText = String(chartData?.axes?.unit || '').trim();
  const isPercentage = isPie || /%|percent/i.test(`${unitText} ${chartData?.axes?.y_label || ''}`);
  const valueSuffix = isPercentage ? '%' : unitText ? ` ${unitText}` : '';
  const deltaSuffix = isPercentage ? ' percentage points' : valueSuffix;
  const formatValue = (value) => `${formatFeedbackNumber(value)}${valueSuffix}`;
  const hasProblems = issues.length > 0 || recordIssues.length > 0 || hasBalanceIssue;
  if (!hasProblems) {
    const tolerance = Number(comparison.accepted_value_tolerance);
    const toleranceUnit = String(comparison.accepted_value_tolerance_unit || '').trim();
    const toleranceMessage = Number.isFinite(tolerance) && tolerance === 0
      ? ' Exact agreement with the rounded official values is required.'
      : Number.isFinite(tolerance)
      ? ` Values mentioned in the essay are within the accepted tolerance (±${formatFeedbackNumber(tolerance)} ${toleranceUnit}).`
      : ' The values mentioned in the essay are consistent with the original chart.';
    return (
      <div
        role="status"
        aria-live="polite"
        style={{
          marginTop: '0.75rem',
          padding: '0.7rem 0 0.1rem 0.75rem',
          borderTop: '1px solid #bbf7d0',
          borderLeft: '4px solid #16a34a',
          color: '#166534',
          fontSize: '0.78rem',
          lineHeight: 1.45,
        }}
      >
        <strong style={{ display: 'block', fontSize: '0.82rem' }}>No data problems detected</strong>
        <div>{toleranceMessage}</div>
      </div>
    );
  }

  const displayedExpectedTotal = Number.isFinite(expectedTotal) ? expectedTotal : 100;
  let totalMessage = hasTotal
    ? `Your total: ${formatFeedbackNumber(total)}%. Expected rounded total: ${formatFeedbackNumber(displayedExpectedTotal)}%.`
    : '';
  if (hasTotal && balance === 'under' && Number.isFinite(difference)) {
    totalMessage += ` Missing ${formatFeedbackNumber(Math.abs(difference))}%.`;
  } else if (hasTotal && balance === 'over' && Number.isFinite(difference)) {
    totalMessage += ` Excess: ${formatFeedbackNumber(Math.abs(difference))}%.`;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        marginTop: '0.75rem',
        paddingTop: '0.7rem',
        borderTop: '1px solid #e5e7eb',
        borderLeft: '4px solid #dc2626',
        paddingLeft: '0.75rem',
        color: '#7f1d1d',
        fontSize: '0.78rem',
        lineHeight: 1.45,
      }}
    >
      <strong style={{ display: 'block', fontSize: '0.82rem' }}>Data issues</strong>
      {totalMessage && <div>{totalMessage}</div>}
      {recordIssues.length > 0 && (
        <div style={{ marginTop: '0.45rem', display: 'grid', gap: '0.45rem' }}>
          {recordIssues.map((record, index) => {
            const category = record.feedback_label || record.category || record.series || record.region || record.period || 'Unknown item';
            const studentValue = Number(record.value);
            const officialValue = Number(record.official_value);
            const hasStudentValue = record.value !== null && record.value !== '' && Number.isFinite(studentValue);
            const hasOfficialValue = record.official_value !== null && record.official_value !== '' && Number.isFinite(officialValue);
            const conflictingValues = Array.isArray(record.conflicting_values)
              ? record.conflicting_values.map(Number).filter(Number.isFinite)
              : [];
            const hasConflict = record.feedback_status === 'conflicting' && conflictingValues.length > 1;
            const delta = hasStudentValue && hasOfficialValue ? studentValue - officialValue : null;
            const studentLabel = hasConflict
              ? conflictingValues.map(formatValue).join(' / ')
              : hasStudentValue
              ? formatValue(studentValue)
              : 'Not mentioned';
            const officialLabel = hasOfficialValue
              ? formatValue(officialValue)
              : 'Not in original chart';

            return (
              <div
                key={`${category}-${index}`}
                style={{ borderTop: '1px solid #fecaca', paddingTop: '0.4rem' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <strong style={{ color: '#450a0a' }}>{category}</strong>
                  {hasConflict ? (
                    <span style={{ color: '#b91c1c', fontWeight: 700 }}>Conflicting values</span>
                  ) : Number.isFinite(delta) && Math.abs(delta) > 0.05 && (
                    <span style={{ color: '#b91c1c', fontWeight: 700 }}>
                      {delta > 0 ? '+' : ''}{formatFeedbackNumber(delta)}{deltaSuffix}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                    gap: '0.5rem',
                    marginTop: '0.3rem',
                  }}
                >
                  <div style={{ borderLeft: '3px solid #dc2626', background: '#fef2f2', padding: '0.35rem 0.5rem' }}>
                    <span style={{ display: 'block', color: '#7f1d1d' }}>
                      {hasConflict ? 'Answers found' : 'Your answer'}
                    </span>
                    <strong style={{ display: 'block', color: '#991b1b', fontSize: '0.95rem' }}>{studentLabel}</strong>
                  </div>
                  <div style={{ borderLeft: '3px solid #16a34a', background: '#f0fdf4', padding: '0.35rem 0.5rem' }}>
                    <span style={{ display: 'block', color: '#14532d' }}>Correct value</span>
                    <strong style={{ display: 'block', color: '#166534', fontSize: '0.95rem' }}>{officialLabel}</strong>
                  </div>
                </div>
                {hasConflict && hasStudentValue && (
                  <div style={{ marginTop: '0.25rem', color: '#7f1d1d' }}>
                    The chart uses the latest value: {formatValue(studentValue)}.
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      {recordIssues.length === 0 && issues.length > 0 && (
        <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.1rem' }}>
          {issues.map((issue, index) => <li key={`${issue}-${index}`}>{issue}</li>)}
        </ul>
      )}
    </div>
  );
}

export default function App() {
  // Dev debug flag (set VITE_SHOW_DEBUG=true in .env to enable)
  const SHOW_DEBUG = import.meta.env.VITE_SHOW_DEBUG === 'true';

  const [authReady, setAuthReady] = useState(false);
  const [passwordRequired, setPasswordRequired] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState(""); // NEW: current logged in user
  const [leftWidth, setLeftWidth] = useState(60); // Percentage width of the left pane
  const [upperHeight, setUpperHeight] = useState(33.33); // Percentage height of the upper section
  // 初始文本为空，使用占位符在聚焦时自动消失
  const [text, setText] = useState("");
  // Stages handling
  const stages = ["planning", "drafting", "revision"];
  const [stageIndex, setStageIndex] = useState(0);
  const currentStage = stages[stageIndex];
  const [showStageConfirm, setShowStageConfirm] = useState(false);
  const [showImageRequired, setShowImageRequired] = useState(false);
  // Sample essay structure choice dialog
  const [showStructureChoice, setShowStructureChoice] = useState(false);
  const [structureChoiceInfo, setStructureChoiceInfo] = useState(null);
  const [pendingSampleEssayRequest, setPendingSampleEssayRequest] = useState(null);
  // Post-login tips modal
  const [showPostLoginTips, setShowPostLoginTips] = useState(false);
  // Stage transition notification removed
  // Save reminder states
  const [showSaveReminder, setShowSaveReminder] = useState(false);
  //修改1
  const [rightContent, setRightContent] = useState("Flowchart");

  useEffect(() => {
    let cancelled = false;

    const restoreSession = async () => {
      try {
        const config = await getAuthConfig();
        if (!cancelled) {
          setPasswordRequired(config?.password_required !== false);
        }
      } catch (error) {
        console.warn('Could not load login settings', error);
      }

      try {
        const session = await getCurrentUser();
        if (!cancelled && session?.authenticated && session?.username) {
          setUsername(session.username);
          setIsLoggedIn(true);
        }
      } catch {
        if (!cancelled) {
          setUsername("");
          setIsLoggedIn(false);
        }
      } finally {
        if (!cancelled) {
          setAuthReady(true);
        }
      }
    };

    const handleUnauthorized = () => {
      setUsername("");
      setIsLoggedIn(false);
      setShowPostLoginTips(false);
    };

    window.addEventListener('vividwrite:unauthorized', handleUnauthorized);
    restoreSession();
    return () => {
      cancelled = true;
      window.removeEventListener('vividwrite:unauthorized', handleUnauthorized);
    };
  }, []);

  useEffect(() => {
    if (currentStage === 'revision') {
      setRightContent('Visual Feedback');
    }
  }, [currentStage]);
  
  const [chartUrl, setChartUrl] = useState(null);
  const [chartData, setChartData] = useState(null);
  // New revision review data (vocabulary / grammar / coherence / overall) with mapped suggestions
  const [revisionReview, setRevisionReview] = useState(null); // {overall:{...}, suggestions:[...]}
  const [reviewSuggestions, setReviewSuggestions] = useState([]); // normalized list with id, category, message, severity, ranges
  const [activeSuggestionId, setActiveSuggestionId] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  //添加图片上传功能
  const [uploadedImage, setUploadedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [selectedChartType, setSelectedChartType] = useState("auto");
  const [resolvedChartType, setResolvedChartType] = useState(null);
  const [taskDetection, setTaskDetection] = useState(null);
  const [isPreparingTaskImage, setIsPreparingTaskImage] = useState(false);
  const [taskPreparationPhase, setTaskPreparationPhase] = useState("");
  const effectiveChartType = selectedChartType === "auto"
    ? (resolvedChartType || "auto")
    : selectedChartType;
  const isSpatialTask = SPATIAL_TASK_TYPES.has(effectiveChartType);
  const isStatisticalTask = STATISTICAL_TASK_TYPES.has(effectiveChartType);
  const [flowchartData, setFlowchartData] = useState({ nodes: [], edges: [] });
  const [isNextSentenceLoading, setIsNextSentenceLoading] = useState(false);
  const [isSampleEssayLoading, setIsSampleEssayLoading] = useState(false); // separate loading state
  const [nextSentenceError, setNextSentenceError] = useState("");
  const [nextSentenceResult, setNextSentenceResult] = useState(null);
  // Next sentence candidate feature
  const [deplotText, setDeplotText] = useState(""); // 保存图像解析出的文本（上传图片后设置）
  const [candidateCount, setCandidateCount] = useState(3); // 1~6
  const [aiCandidates, setAiCandidates] = useState([]); // 返回的候选列表
  const [showCandidatePanel, setShowCandidatePanel] = useState(false);
  const [parseMode, setParseMode] = useState("");
  // DePlot extraction states
  const [isExtractingDeplot, setIsExtractingDeplot] = useState(false);
  const [deplotError, setDeplotError] = useState("");
  const taskImagePreparationRef = useRef({ seq: 0, promise: null, key: null });
  // Track background DePlot extraction task without showing UI
  const deplotTaskRef = useRef({ seq: 0, promise: null, key: null });
  // Helper to run DePlot extraction; if showOverlay=true, show analyzing modal while waiting
  const runDeplotExtraction = useCallback(async (
    file,
    { showOverlay = false, chartTypeOverride = null } = {}
  ) => {
    if (!file) return Promise.reject(new Error('No image file'));
    const deplotChartType = chartTypeOverride || effectiveChartType;
    if (!STATISTICAL_TASK_TYPES.has(deplotChartType)) {
      return Promise.reject(new Error('Please confirm a statistical chart type before DePlot extraction.'));
    }
    const taskKey = [
      file.name,
      file.size,
      file.lastModified,
      deplotChartType,
    ].join(':');
    const activeTask = deplotTaskRef.current;
    if (activeTask.promise && activeTask.key === taskKey) {
      return activeTask.promise;
    }

    // bump sequence to invalidate older responses when starting a new task
    const seq = ++deplotTaskRef.current.seq;
    const fd = new FormData();
    fd.append('image', file);
    fd.append('chart_type', deplotChartType);
    const exec = async () => {
      try {
        if (showOverlay) setIsExtractingDeplot(true);
        const res = await extractDeplot(fd);
        // Only apply if latest
        if (deplotTaskRef.current.seq === seq) {
          if (res?.extracted_text && res.extracted_text.trim()) {
            setDeplotText(res.extracted_text);
            setDeplotError("");
          } else {
            setDeplotError('DePlot returned empty result');
          }
        }
        return res;
      } catch (e) {
        if (deplotTaskRef.current.seq === seq) {
          setDeplotError(e.message || 'DePlot extraction failed');
        }
        throw e;
      } finally {
        if (showOverlay) setIsExtractingDeplot(false);
        // clear stored promise when this task completes (only if still current)
        if (deplotTaskRef.current.seq === seq) {
          deplotTaskRef.current = {
            seq,
            promise: null,
            key: taskKey,
          };
        }
      }
    };
    const p = exec();
    deplotTaskRef.current = {
      seq,
      promise: p,
      key: taskKey,
    };
    return p;
  }, [effectiveChartType]);

  const ensureDeplotText = useCallback(async (
    file,
    { errorPrefix = 'DePlot extraction failed', chartTypeOverride = null } = {},
  ) => {
    const cachedText = deplotText.trim();
    if (cachedText) return deplotText;
    if (!file) throw new Error('Please upload an image first.');

    setIsExtractingDeplot(true);
    try {
      const pendingTask = deplotTaskRef.current?.promise;
      const res = pendingTask
        ? await pendingTask
        : await runDeplotExtraction(file, { showOverlay: false, chartTypeOverride });

      const extracted = res?.extracted_text?.trim() ? res.extracted_text : '';
      if (!extracted) {
        throw new Error('DePlot returned empty result. Please try a clearer chart image.');
      }

      setDeplotText(extracted);
      setDeplotError('');
      return extracted;
    } catch (e) {
      const message = e?.message || errorPrefix;
      setDeplotError(message);
      throw new Error(`${errorPrefix}: ${message}`);
    } finally {
      setIsExtractingDeplot(false);
    }
  }, [deplotText, runDeplotExtraction]);

  const prepareUploadedTaskImage = useCallback(async (
    file,
    selectedTypeOverride = selectedChartType,
  ) => {
    if (!file) return null;
    const selectedType = selectedTypeOverride || "auto";
    const taskKey = [
      file.name,
      file.size,
      file.lastModified,
      selectedType,
    ].join(':');
    const activeTask = taskImagePreparationRef.current;
    if (activeTask.promise && activeTask.key === taskKey) {
      return activeTask.promise;
    }

    const seq = activeTask.seq + 1;
    const exec = async () => {
      setIsPreparingTaskImage(true);
      setTaskPreparationPhase(selectedType === "auto" ? "detecting" : "");
      try {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('chart_type', selectedType);
        formData.append('extract_deplot', 'false');
        const result = await prepareTaskImage(formData);
        if (taskImagePreparationRef.current.seq !== seq) {
          return result;
        }

        setTaskDetection(result || null);
        if (selectedType === "auto") {
          if (result?.needs_confirmation || !KNOWN_TASK_TYPES.has(result?.task_type)) {
            setResolvedChartType(null);
            setIsExtractingDeplot(false);
            setDeplotError(
              'Auto Detect could not confidently identify this image. Please choose Map Task, Process Diagram, or a chart type manually.'
            );
            return result;
          }
          setResolvedChartType(result.task_type);
        } else {
          setResolvedChartType(null);
        }

        const preparedType = selectedType === "auto" ? result?.task_type : selectedType;
        if (STATISTICAL_TASK_TYPES.has(preparedType)) {
          if (result?.deplot_text?.trim()) {
            setDeplotText(result.deplot_text);
            setDeplotError("");
          } else {
            setTaskPreparationPhase("deplot");
            await runDeplotExtraction(file, {
              showOverlay: false,
              chartTypeOverride: preparedType,
            }).catch(() => null);
          }
        } else {
          setDeplotText("");
          setDeplotError("");
          setIsExtractingDeplot(false);
        }
        return result;
      } catch (error) {
        if (taskImagePreparationRef.current.seq === seq) {
          setTaskDetection({
            task_type: "unknown",
            confidence: 0,
            needs_confirmation: true,
            detection_source: "frontend-error",
            error: error.message,
          });
          setResolvedChartType(null);
          setIsExtractingDeplot(false);
          setDeplotError(error.message || 'Task type detection failed. Please choose the task type manually.');
        }
        throw error;
      } finally {
        if (taskImagePreparationRef.current.seq === seq) {
          taskImagePreparationRef.current = {
            seq,
            promise: null,
            key: taskKey,
          };
          setIsPreparingTaskImage(false);
          setTaskPreparationPhase("");
        }
      }
    };

    const promise = exec();
    taskImagePreparationRef.current = {
      seq,
      promise,
      key: taskKey,
    };
    return promise;
  }, [runDeplotExtraction, selectedChartType]);

  const resolveTaskTypeForAction = useCallback(async () => {
    const currentType = selectedChartType === "auto" ? resolvedChartType : selectedChartType;
    if (KNOWN_TASK_TYPES.has(currentType)) {
      return currentType;
    }
    if (!uploadedImage) {
      throw new Error('Please upload an image first.');
    }

    const taskKey = [
      uploadedImage.name,
      uploadedImage.size,
      uploadedImage.lastModified,
      selectedChartType,
    ].join(':');
    const activeTask = taskImagePreparationRef.current;
    const result = activeTask.promise && activeTask.key === taskKey
      ? await activeTask.promise
      : await prepareUploadedTaskImage(uploadedImage, selectedChartType);
    const resolvedType = selectedChartType === "auto" ? result?.task_type : selectedChartType;
    if (result?.needs_confirmation || !KNOWN_TASK_TYPES.has(resolvedType)) {
      throw new Error(
        'Auto Detect could not confidently identify this image. Please choose Map Task, Process Diagram, or a chart type manually.'
      );
    }
    return resolvedType;
  }, [prepareUploadedTaskImage, resolvedChartType, selectedChartType, uploadedImage]);
  const [missingNodes, setMissingNodes] = useState([]); // array of {id,title,reason}
  const [sentenceRanges, setSentenceRanges] = useState([]); // [{index,start,end,text}]
  const [paragraphRanges, setParagraphRanges] = useState([]); // [{paragraph_index,start,end,text}]
  const [structureFeedback, setStructureFeedback] = useState(null);
  const [mappingStatus, setMappingStatus] = useState('idle'); // idle | loading | ok | missing | error
  const [nodeToSentenceIndices, setNodeToSentenceIndices] = useState({}); // { nodeId: [sentenceIndex,...] }
  const [nodeToParagraphIndices, setNodeToParagraphIndices] = useState({}); // { nodeId: [paragraphIndex,...] }
  const [lastAddition, setLastAddition] = useState(null); // { start,end,prevText }
  const editorRef = useRef(null);

  useEffect(() => {
    if (rightContent !== 'Flowchart') {
      editorRef.current?.clearHighlights();
      setActiveSuggestionId(null);
    }
  }, [rightContent]);

  const buildHighlightRanges = (indices, ranges, indexKey = 'index') => {
    if (!Array.isArray(indices) || !Array.isArray(ranges)) {
      return [];
    }
    return indices.map(i => {
      const range = ranges.find(item => item[indexKey] === i);
      if (!range) return null;
      return { from: range.start, to: range.end };
    }).filter(Boolean);
  };

  const runStructureAnalyze = useCallback(() => {
    setMappingStatus('loading');
    if (!uploadedImage || !text.trim() || !flowchartData?.nodes?.length) {
      setMappingStatus('idle');
      return;
    }
    analyzeStructure({
      current_text: text,
      flowchart: flowchartData,
      deplot_text: deplotText || null,
      chart_type: effectiveChartType,
    })
      .then(res => {
        if (res.error) {
          setMappingStatus('error');
          return;
        }
        const sentences = res.sentences || [];
        const paragraphs = res.paragraphs || [];
        setSentenceRanges(sentences);
        setParagraphRanges(paragraphs);
        setStructureFeedback(res.structure_feedback || null);

        const sentenceNodeMap = {};
        (res.mappings || []).forEach(mapping => {
          const nodeIds = mapping.node_ids?.length
            ? mapping.node_ids
            : mapping.primary_node
              ? [mapping.primary_node]
              : [];
          nodeIds.forEach(nodeId => {
            if (!sentenceNodeMap[nodeId]) sentenceNodeMap[nodeId] = [];
            sentenceNodeMap[nodeId].push(mapping.sentence_index);
          });
        });
        Object.keys(sentenceNodeMap).forEach(nodeId => {
          sentenceNodeMap[nodeId] = Array.from(new Set(sentenceNodeMap[nodeId])).sort((a, b) => a - b);
        });

        const paragraphNodeMap = {};
        (res.paragraph_mappings || []).forEach(mapping => {
          if (mapping.primary_node) {
            if (!paragraphNodeMap[mapping.primary_node]) {
              paragraphNodeMap[mapping.primary_node] = [];
            }
            paragraphNodeMap[mapping.primary_node].push(mapping.paragraph_index);
          }
        });
        Object.keys(paragraphNodeMap).forEach(nodeId => {
          paragraphNodeMap[nodeId] = Array.from(new Set(paragraphNodeMap[nodeId])).sort((a, b) => a - b);
        });

        const reportedMissingNodes = res.missing_nodes || [];
        setNodeToSentenceIndices(sentenceNodeMap);
        setNodeToParagraphIndices(paragraphNodeMap);
        setMissingNodes(reportedMissingNodes);
        setMappingStatus(reportedMissingNodes.length ? 'missing' : 'ok');
      })
      .catch(err => {
        console.warn('Mapping error', err);
        setMappingStatus('error');
      });
  }, [text, flowchartData, uploadedImage, deplotText, effectiveChartType]);

  const handleNodeClickHighlight = (nodeId) => {
    if (!editorRef.current) {
      return;
    }
    if (!['ok', 'missing'].includes(mappingStatus)) {
      return;
    }
    setActiveSuggestionId(null);
    const paragraphHighlights = buildHighlightRanges(
      nodeToParagraphIndices[nodeId] || [],
      paragraphRanges,
      'paragraph_index',
    );
    const sentenceHighlights = buildHighlightRanges(
      nodeToSentenceIndices[nodeId] || [],
      sentenceRanges,
    );
    const ranges = paragraphHighlights.length ? paragraphHighlights : sentenceHighlights;
    if (ranges.length === 0) {
      return;
    }
    editorRef.current.clearHighlights();
    editorRef.current.highlightSentenceRanges(ranges);
  };

  const handleLogin = async (uname, password) => {
    const session = await loginUser(uname, password);
    setUsername(session.username);
    setIsLoggedIn(true);
    // Show tips modal right after login
    setShowPostLoginTips(true);
  };

  const handleLogout = async () => {
    await logoutUser();
    setUsername("");
    setIsLoggedIn(false);
    setShowPostLoginTips(false);
  };

  const handleNextStage = async () => {
    console.log('Next Stage clicked:', { stageIndex, currentStage, hasImage: !!uploadedImage, hasText: !!text.trim() });
    // If already at last stage do nothing
    if (stageIndex === stages.length - 1) {
      console.log('Already at last stage');
      return;
    }
    // Require image uploaded before any stage advance
    if (!uploadedImage) {
      setShowImageRequired(true);
      return;
    }

    // Only show save reminder in revision stage (not in drafting)
    if (text.trim() && currentStage === 'revision') {
      console.log('Has unsaved text in revision, showing save reminder');
      setShowSaveReminder(true);
      return;
    }

    // Keep DePlot extraction in the background. Stage changes should not be blocked by
    // first-time model loading or a slow chart parse.
    if (currentStage === 'planning' && isStatisticalTask) {
      setIsExtractingDeplot(false);
      if (!deplotText.trim() && !deplotTaskRef.current?.promise) {
        runDeplotExtraction(uploadedImage, { showOverlay: false }).catch(() => {
          // Error is already stored in deplotError; users can still continue drafting.
        });
      }
    }

    setShowStageConfirm(true);
  };

  const confirmStageAdvance = async () => {
    setShowStageConfirm(false);
    
    // Save final image when leaving planning (non-blocking)
    setDeplotError("");
    const movingFromPlanning = stages[stageIndex] === 'planning' && stageIndex < stages.length - 1;
    if (movingFromPlanning && username && uploadedImage) {
      saveFinalImage(username, uploadedImage).catch(e => console.warn('Failed to save final image', e));
    }

    // 更新stage索引（若上面未提前返回）
    setStageIndex((prev) => Math.min(prev + 1, stages.length - 1));
    
    // Removed stage transition toast
  };

  const cancelStageAdvance = () => setShowStageConfirm(false);
  
  const handleSaveReminderConfirm = () => {
    setShowSaveReminder(false);
    setShowStageConfirm(true);
  };
  
  const handleSaveReminderCancel = () => {
    setShowSaveReminder(false);
  };

  // Keep rightContent consistent with stage rules (now allow Flowchart also in revision)
  useEffect(() => {
    if (currentStage === 'planning' || currentStage === 'drafting') {
      if (rightContent !== 'Flowchart') setRightContent('Flowchart');
    } else if (currentStage === 'revision') {
      // In revision we now allow Flowchart to stay; just close candidate panel
      setShowCandidatePanel(false);
    }
  }, [currentStage, rightContent]);

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadedImage(file);
      setChartUrl(null);
      setChartData(null);
      // 创建预览URL
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target.result);
      };
      reader.readAsDataURL(file);
      // Reset previous DePlot results and errors
      setDeplotText("");
      setDeplotError("");
      setTaskDetection(null);
      setResolvedChartType(null);
      prepareUploadedTaskImage(file, selectedChartType).catch(() => {
        // Error is already stored in deplotError; users can manually choose the task type.
      });
    }
  };

  const handleRemoveImage = () => {
    setUploadedImage(null);
    setImagePreview(null);
    setChartUrl(null);
    setChartData(null);
    taskImagePreparationRef.current = {
      seq: taskImagePreparationRef.current.seq + 1,
      promise: null,
      key: null,
    };
    // Invalidate any pending DePlot extraction and clear related state
    deplotTaskRef.current = {
      seq: deplotTaskRef.current.seq + 1,
      promise: null,
      key: null,
    };
    setDeplotText("");
    setDeplotError("");
    setTaskDetection(null);
    setResolvedChartType(null);
    setIsPreparingTaskImage(false);
    setTaskPreparationPhase("");
  };
//修改2
    // 默认显示Visual Feedback
  const handleAnalyzeText = async () => {
    if (!text.trim()) {
  setAnalysisError("Please enter text to analyze");
      return;
    }
    if (!uploadedImage) {
  setAnalysisError("Please upload the original image first");
      return;
    }

    let taskTypeForAnalysis;
    try {
      taskTypeForAnalysis = await resolveTaskTypeForAction();
    } catch (error) {
      setAnalysisError(error.message);
      return;
    }
    const analysisIsSpatial = SPATIAL_TASK_TYPES.has(taskTypeForAnalysis);

    // Persist revision full text snapshot
    if (currentStage === 'revision' && username) {
      try { await saveRevisionText(username, text); } catch (e) { console.warn('Failed to save revision text', e); }
    }

    setIsAnalyzing(true);
    setAnalysisError("");
    setChartUrl(null);
    setChartData(null);

    let deplotForAnalysis = analysisIsSpatial ? '(Not required for spatial tasks)' : deplotText;
    if (!analysisIsSpatial && !deplotForAnalysis.trim()) {
      try {
        deplotForAnalysis = await ensureDeplotText(uploadedImage, {
          errorPrefix: 'Automatic DePlot extraction failed',
          chartTypeOverride: taskTypeForAnalysis,
        });
      } catch {
        setDeplotError("Automatic DePlot extraction failed, continuing with placeholder text");
      }
    }

    try {
      if (currentStage === 'revision') {
        // Run BOTH: LLM revision review + chart analysis for visual feedback.
        if (!deplotForAnalysis.trim()) deplotForAnalysis = '(No DePlot data extracted)';
        const reviewPromise = reviewRevision({ text, flowchart: flowchartData, deplot_text: deplotForAnalysis, mode: 'llm' });
        // prepare chart form data (reuse existing logic)
        const formData = new FormData();
        formData.append('image', uploadedImage);
        formData.append('chart_type', taskTypeForAnalysis);
        const requirement = analysisRequirement(taskTypeForAnalysis);
        formData.append('requirement', requirement);
        formData.append('student_answer', text);
        formData.append('deplot_text', deplotForAnalysis);
        const chartPromise = analyzeChartWithImage(formData);
        const [reviewRes, chartRes] = await Promise.allSettled([reviewPromise, chartPromise]);
        // helper to normalize chart URL (backend returns /charts/.. relative to backend origin)
        if (reviewRes.status === 'fulfilled' && reviewRes.value.success) {
          console.log('Revision review response:', reviewRes.value);
          console.log('Total suggestions received:', (reviewRes.value.suggestions || []).length);
          console.log('Suggestions by category:', reviewRes.value.suggestions_by_category);
          setRevisionReview(reviewRes.value.overall);
          setReviewSuggestions(reviewRes.value.suggestions || []);
        } else if (reviewRes.status === 'fulfilled') {
          setAnalysisError(reviewRes.value.error || 'Revision review failed');
        } else {
          setAnalysisError(reviewRes.reason?.message || 'Revision review failed');
        }
        if (chartRes.status === 'fulfilled' && chartRes.value.success) {
          setChartUrl(resolveBackendUrl(chartRes.value.chart_url));
          setChartData(chartRes.value.chart_data || null);
        } else if (chartRes.status === 'fulfilled') {
          setAnalysisError(prev => prev ? prev + '; ' + (chartRes.value.error || 'Chart analysis failed') : (chartRes.value.error || 'Chart analysis failed'));
        } else {
          setAnalysisError(prev => prev ? prev + '; ' + (chartRes.reason?.message || 'Chart analysis failed') : (chartRes.reason?.message || 'Chart analysis failed'));
        }
        // remove older simple revisionSuggestions list (not used in revision now)
      } else {
        // Planning/drafting keep previous analyze (chart + simple suggestions)
        const formData = new FormData();
        formData.append('image', uploadedImage);
        formData.append('chart_type', taskTypeForAnalysis);
        const requirement = analysisRequirement(taskTypeForAnalysis);
        formData.append('requirement', requirement);
        formData.append('student_answer', text);
        if (!deplotForAnalysis.trim()) deplotForAnalysis = '(No DePlot data extracted)';
        formData.append('deplot_text', deplotForAnalysis);
        const result = await analyzeChartWithImage(formData);
        if (result.success) {
          setChartUrl(resolveBackendUrl(result.chart_url));
          setChartData(result.chart_data || null);
        } else {
          setAnalysisError(result.error || "分析失败");
        }
      }
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Apply a single suggestion: replace its excerpt with replacement and adjust subsequent suggestion ranges
  const applySuggestion = useCallback((sug) => {
    if (!sug || sug.applied) return;
    setText(prevText => {
      let working = prevText;
      // resolve current range (may be outdated after edits)
      let range = sug.range || (Array.isArray(sug.ranges) && sug.ranges[0]);
      const excerpt = sug.excerpt;
      const locateFresh = () => {
        if (!excerpt) return null;
        const idx = working.indexOf(excerpt);
        if (idx === -1) return null;
        return { start: idx, end: idx + excerpt.length };
      };
      if (!range || working.slice(range.start, range.end) !== excerpt) {
        range = locateFresh();
      }
      if (!range) {
        // Cannot apply; keep text unchanged but flag suggestion as invalid
        setReviewSuggestions(old => old.map(s => s.id === sug.id ? { ...s, applyError: '原文片段已找不到，无法自动替换' } : s));
        return working;
      }
      const before = working.slice(0, range.start);
      const after = working.slice(range.end);
      const newText = before + sug.replacement + after;
      const delta = sug.replacement.length - (range.end - range.start);
      // Update suggestions state (ranges & applied flag)
      setReviewSuggestions(old => old.map(s => {
        if (s.id === sug.id) {
          const newRange = { start: range.start, end: range.start + sug.replacement.length };
            return { ...s, applied: true, range: newRange, ranges: [newRange], appliedAt: Date.now() };
        }
        if (s.applied) return s; // already fixed
        // Adjust later ranges by simple shift; if mismatch after shift, attempt re-locate
        if (Array.isArray(s.ranges) && s.ranges[0]) {
          let r0 = s.ranges[0];
          // Only shift if the original start is after replaced segment end
          if (r0.start >= range.end) {
            const shifted = { start: r0.start + delta, end: r0.end + delta };
            return { ...s, range: shifted, ranges: [shifted] };
          } else {
            // If overlapping or before, verify excerpt still matches; if not, try fresh search
            const currentText = newText;
            if (currentText.slice(r0.start, r0.end) !== s.excerpt) {
              const idx2 = s.excerpt ? currentText.indexOf(s.excerpt) : -1;
              if (idx2 !== -1) {
                const newRange = { start: idx2, end: idx2 + s.excerpt.length };
                return { ...s, range: newRange, ranges: [newRange] };
              } else {
                return { ...s, no_range: true }; // mark unusable
              }
            }
          }
        }
        return s;
      }));
      // Highlight the newly inserted text asynchronously
      setTimeout(() => {
        if (editorRef.current) {
          const start = range.start;
          const end = start + sug.replacement.length;
          editorRef.current.clearHighlights();
          editorRef.current.highlightRange(start, end, true);
        }
      }, 0);
      return newText;
    });
  }, [setText, setReviewSuggestions, editorRef]);

  const handleNextSentence = async (e) => {
    try {
      const quickAccept = e && e.shiftKey; // Shift+Click 快速使用第一条
      setNextSentenceError("");
      setNextSentenceResult(null);
      setLastAddition(null);
      setAiCandidates([]);
      setShowCandidatePanel(false);
      let taskTypeForNextSentence;
      try {
        taskTypeForNextSentence = await resolveTaskTypeForAction();
      } catch (error) {
        setNextSentenceError(error.message);
        return;
      }
      if (SPATIAL_TASK_TYPES.has(taskTypeForNextSentence)) {
        setNextSentenceError('Next Sentence for map/process tasks needs a vision-language model and is not enabled yet.');
        return;
      }
      if (!uploadedImage) {
        setNextSentenceError("Please upload an image first.");
        return;
      }
      if (!text || !text.trim()) {
        setNextSentenceError("Please enter some text before requesting the next sentence.");
        return;
      }
      if (!deplotText.trim()) {
        setNextSentenceError("Missing chart textual data (deplot). Please analyze chart first.");
        return;
      }
      setIsNextSentenceLoading(true);
  const payload = { current_text: text, flowchart: flowchartData, deplot_text: deplotText, candidate_count: candidateCount };
      let res;
      try { res = await requestNextSentence(payload); } catch (apiErr) { if (import.meta.env.VITE_SHOW_DEBUG==='true') console.error('requestNextSentence failed', apiErr); throw apiErr; }
      setNextSentenceResult(res);
      setParseMode(res?.debug?.parse_mode || "");
      const cands = Array.isArray(res?.candidates) ? res.candidates.filter(c => c && c.trim()) : [];
      if (!cands.length) {
        setNextSentenceError('No candidates returned');
        return;
      }
      setAiCandidates(cands);
      if (quickAccept) {
        // 直接使用第一条
        insertCandidate(cands[0]);
      } else {
        setShowCandidatePanel(true);
      }
    } catch (e) {
      setNextSentenceError(e.message || 'Failed to generate sentence');
    } finally {
      setIsNextSentenceLoading(false);
    }
  };

  const handleGenerateSampleEssay = async () => {
    if (!uploadedImage) {
      setNextSentenceError("Please upload an image first.");
      return;
    }
    setNextSentenceError("");
    let taskTypeForSampleEssay;
    try {
      taskTypeForSampleEssay = await resolveTaskTypeForAction();
    } catch (error) {
      setNextSentenceError(error.message);
      return;
    }
    const sampleEssayIsSpatial = SPATIAL_TASK_TYPES.has(taskTypeForSampleEssay);
    let dep = "";
    if (!sampleEssayIsSpatial) {
      try {
        dep = await ensureDeplotText(uploadedImage, {
          errorPrefix: 'Failed to extract DePlot data for sample essay',
          chartTypeOverride: taskTypeForSampleEssay,
        });
      } catch (e) {
        setNextSentenceError(e.message || 'Failed to extract DePlot data for sample essay');
        return;
      }
    }

    try {
      setIsSampleEssayLoading(true);
      const requirement = sampleEssayRequirement(taskTypeForSampleEssay);
      const requestData = sampleEssayIsSpatial
        ? { image: uploadedImage, flowchart: flowchartData, requirement, chart_type: taskTypeForSampleEssay }
        : { deplot_text: dep, flowchart: flowchartData, requirement, chart_type: taskTypeForSampleEssay };
      const requestKind = sampleEssayIsSpatial ? 'spatial' : 'statistical';
      const res = sampleEssayIsSpatial
        ? await generateSpatialSampleEssay(requestData)
        : await generateSampleEssay(requestData);
      
      if (res.requires_choice) {
        // Show structure choice dialog
        setStructureChoiceInfo(res.choice_info);
        setShowStructureChoice(true);
        setPendingSampleEssayRequest({ kind: requestKind, data: requestData });
        return;
      }
      
      if (res.success && res.essay) {
        setText(res.essay);
        // Clear existing highlights
        if (editorRef.current) editorRef.current.clearHighlights();
      } else {
        setNextSentenceError(res.error || 'Sample essay generation failed');
      }
    } catch (e) {
      setNextSentenceError(e.message || 'Sample essay generation failed');
    } finally {
      setIsSampleEssayLoading(false);
    }
  };

  // Handle structure choice for sample essay
  const handleStructureChoice = async (useStandardStructure) => {
    if (!pendingSampleEssayRequest) return;
    
    try {
      setIsSampleEssayLoading(true);
      const updatedRequest = {
        ...pendingSampleEssayRequest.data,
        use_standard_structure: useStandardStructure
      };
      
      const res = pendingSampleEssayRequest.kind === 'spatial'
        ? await generateSpatialSampleEssay(updatedRequest)
        : await generateSampleEssay(updatedRequest);
      
      if (res.success && res.essay) {
        setText(res.essay);
        // Clear existing highlights
        if (editorRef.current) editorRef.current.clearHighlights();
      } else {
        setNextSentenceError(res.error || 'Sample essay generation failed');
      }
    } catch (e) {
      setNextSentenceError(e.message || 'Sample essay generation failed');
    } finally {
      setIsSampleEssayLoading(false);
      setShowStructureChoice(false);
      setStructureChoiceInfo(null);
      setPendingSampleEssayRequest(null);
    }
  };

  const insertCandidate = (sentenceRaw) => {
    if (!sentenceRaw) return;
    const clean = sentenceRaw.replace(/\s+/g, ' ').trim();
    setText(prev => {
      if (!clean) return prev;
      const prevText = prev;
      const prefix = (prev.endsWith('\n') || prev.endsWith(' ')) ? '' : ' ';
      const addition = prefix + clean;
      const newValue = prev + addition;
      const start = prev.length;
      const end = newValue.length;
      setLastAddition({ sentence: addition, prevText, start, end });
      return newValue;
    });
    setShowCandidatePanel(false);
    // Adding candidate invalidates active suggestion highlight (content changed)
    setActiveSuggestionId(null);
  };

  // Highlight newly added sentence AFTER text value is committed to editor
  useEffect(() => {
    if (!lastAddition) return;
    if (!editorRef.current) return;
    const { start, end } = lastAddition;
    // Clamp again defensively vs any async race
    const docLen = editorRef.current.getValue().length;
    if (start >= 0 && end <= docLen && end > start) {
      editorRef.current.clearHighlights();
      editorRef.current.highlightRange(start, end, true);
    }
  }, [lastAddition, text]);
  
  // Persist active suggestion highlight across re-renders / typing
  useEffect(() => {
    if (!editorRef.current) return;
    if (!activeSuggestionId) return; // nothing to persist
    const sug = reviewSuggestions.find(s => s.id === activeSuggestionId);
    if (!sug) return;
    const range = sug.range || (Array.isArray(sug.ranges) && sug.ranges[0]);
    if (!range) return;
    let { start, end } = range;
    const textValue = editorRef.current.getValue();
    const len = textValue.length;
    // Basic boundary validation; if invalid try to locate by excerpt
    if (start < 0 || end > len || start >= end) {
      if (sug.excerpt) {
        const idx = textValue.indexOf(sug.excerpt);
        if (idx !== -1) {
          start = idx; end = idx + sug.excerpt.length;
        } else {
          return; // can't re-highlight
        }
      } else {
        return;
      }
    }
    // Re-apply highlight (clears previous suggestion highlight)
    editorRef.current.clearHighlights();
    // 使用持久高亮（false => persistent），避免 3.5s 自动清除
    editorRef.current.highlightRange(start, end, false);
  }, [activeSuggestionId, reviewSuggestions, text]);

  const handleMouseDownHorizontal = (e) => {
    const startY = e.clientY;
    const startHeight = upperHeight;

    const handleMouseMove = (e) => {
      const delta = e.clientY - startY;
      const newHeight = Math.min(Math.max(startHeight + (delta / window.innerHeight) * 100, 10), 90);
      setUpperHeight(newHeight);
    };

    const handleMouseUp = () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  const handleMouseDownVertical = (e) => {
    const startX = e.clientX;
    const startWidth = leftWidth;

    const handleMouseMove = (e) => {
      const delta = e.clientX - startX;
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 10), 90);
      setLeftWidth(newWidth);
    };

    const handleMouseUp = () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  const handleUndoAddition = () => {
    if (!lastAddition) return;
    setText(lastAddition.prevText);
    setLastAddition(null);
    // Removed notification state reset
    setActiveSuggestionId(null);
  };

  return (
    <>
    <main className="app-shell" style={{ margin: 0, padding: 0, fontFamily: "system-ui, sans-serif", height: "100vh", width: "100vw", display: "flex", flexDirection: "column" }}>
      {!authReady ? (
        <section className="login-root" role="status" aria-live="polite">
          <div className="login-shell">
            <header className="login-brand">
              <span className="login-brand-mark">V</span>
              <span>
                <strong>VividWrite</strong>
                <small>IELTS Writing Studio</small>
              </span>
            </header>
            <p className="login-footnote">Checking session...</p>
          </div>
        </section>
      ) : isLoggedIn ? (
        <ErrorBoundary>
        <>
          {showPostLoginTips && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 3000 }}>
              <div style={{ background: '#fff', padding: '1.75rem 1.5rem 1.25rem', borderRadius: '10px', width: '440px', maxWidth: '90%', boxShadow: '0 6px 20px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.95rem', lineHeight: 1.5 }}>
                <h2 style={{ margin: 0, fontSize: '1.2rem', textAlign: 'center' }}>Welcome to Vividwrite 2.0</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                  <div><strong>Quick Start:</strong></div>
                  <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    <li>Upload the task chart image in the top-left and choose the chart type.</li>
                    <li>Use the Flowchart on the right to plan structure; drag nodes or add Body paragraphs.</li>
                    <li>Click the top "Next Stage" button to drafting stage when you finish.</li>
                  </ul>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', marginTop: '0.25rem' }}>
                  <button onClick={() => setShowPostLoginTips(false)} style={{ padding: '0.55rem 1.4rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500 }}>OK</button>
                </div>
              </div>
            </div>
          )}
          <nav className="app-header" style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            backgroundColor: "#333",
            color: "white",
            padding: "1rem",
            flexShrink: 0,
          }}>
            <div className="brand-lockup" style={{ fontWeight: 700, fontSize: '1.15rem', letterSpacing: '.5px' }}>
              <span className="brand-mark">V</span>
              <span><strong>VividWrite</strong><small>IELTS Writing Studio</small></span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div style={{ fontSize: '0.9rem', background: '#555', padding: '0.4rem 0.75rem', borderRadius: '4px' }}>
                  <strong>Stage:</strong> {currentStage.charAt(0).toUpperCase() + currentStage.slice(1)}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.8rem', color: '#ccc' }}>
                  {stages.map((stage, index) => (
                    <div key={stage} style={{ display: 'flex', alignItems: 'center' }}>
                      <div style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: index <= stageIndex ? '#28a745' : '#666',
                        border: index === stageIndex ? '2px solid #fff' : 'none'
                      }} />
                      {index < stages.length - 1 && (
                        <div style={{
                          width: '12px',
                          height: '1px',
                          background: index < stageIndex ? '#28a745' : '#666',
                          margin: '0 0.25rem'
                        }} />
                      )}
                    </div>
                  ))}
                </div>
              </div>
              {/* Removed inline status badges in favor of modal */}
              <button
                className="next-stage-button"
                onClick={() => {
                  console.log('Button clicked!', { stageIndex, stagesLength: stages.length, disabled: stageIndex === stages.length - 1 });
                  handleNextStage();
                }}
                disabled={stageIndex === stages.length - 1}
                style={{
                  background: stageIndex === stages.length - 1 ? '#555' : '#007bff',
                  color: 'white',
                  border: 'none',
                  padding: '0.5rem 0.9rem',
                  borderRadius: '4px',
                  cursor: stageIndex === stages.length - 1 ? 'not-allowed' : 'pointer',
                  fontSize: '0.9rem',
                  opacity: stageIndex === stages.length - 1 ? 0.6 : 1
                }}
                title="Go to next stage"
              >
                Next Stage <ArrowRight size={15} />
              </button>
              <span style={{ color: '#ddd', fontSize: '0.8rem', fontWeight: 600 }}>
                {username}
              </span>
              <button
                className="icon-button"
                type="button"
                onClick={handleLogout}
                aria-label="Log out"
                title="Log out"
                style={{
                  width: 34,
                  height: 34,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  background: '#4a4a4a',
                  border: '1px solid #666',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                <LogOut size={16} />
              </button>
            </div>
          </nav>
          {showStageConfirm && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 }}>
              <div style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', width: '420px', boxShadow: '0 4px 16px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  Stage Transition Confirmation
                </h3>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>
                  <div style={{ marginBottom: '0.75rem' }}>
                    You will move from <strong style={{ color: '#007bff' }}>{currentStage}</strong> to <strong style={{ color: '#28a745' }}>{stages[stageIndex + 1]}</strong> stage.
                  </div>  
                  <div style={{ marginBottom: '0.75rem' }}>
                    {currentStage === 'planning' && (
                      <>
                        Functions of AI generating would be included in drafting stage:
                      </>
                    )}
                    {currentStage === 'drafting' && (
                      <>
                        <div>
                          Functions of AI generating would be disabled in revision stage (except for "Analyze Structure").
                        </div>
                        <div>
                          Functions of Visual Feedback and Revision Suggestions would be included:
                        </div>
                      </>
                    )}
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.85rem', color: '#6c757d' }}>
                    {currentStage === 'planning' && (
                      <>
                        <li>Next Sentence: AI would suggest the next sentence based on the original image and your flowchart</li>
                        <li>Sample Essay: AI would generate a sample essay based on the original image and your flowchart.</li>
                        <li>Analyze Structure: AI would build the relationship between your essay and flowchart.</li>
                      </>
                    )}
                    {currentStage === 'drafting' && (
                      <>
                        <li>Visual Feedback: AI would generate a graph based on your essay, with similar style of layout and design.</li>
                        <li>Revision Suggestions: AI would provide suggestions for improving your essay based from from different aspects.</li>
                      </>
                    )}
                  </ul>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                  <button onClick={cancelStageAdvance} style={{ padding: '0.45rem 0.9rem', background: '#e0e0e0', border: '1px solid #ccc', borderRadius: 4, cursor: 'pointer' }}>Cancel</button>
                  <button onClick={confirmStageAdvance} style={{ padding: '0.45rem 0.9rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Confirm</button>
                </div>
              </div>
            </div>
          )}
          
          {/* Structure Choice Dialog */}
          {showStructureChoice && structureChoiceInfo && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 }}>
              <div style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', width: '480px', boxShadow: '0 4px 16px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {structureChoiceInfo.title}
                </h3>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>
                  <div style={{ marginBottom: '0.75rem' }}>
                    {structureChoiceInfo.message}
                  </div>
                  <div style={{ marginBottom: '0.75rem', padding: '0.75rem', background: '#f8f9fa', borderRadius: '4px', border: '1px solid #e9ecef' }}>
                    <strong style={{ color: '#dc3545' }}>Missing structures:</strong>
                    <ul style={{ margin: '0.5rem 0 0 1.2rem', padding: 0 }}>
                      {structureChoiceInfo.missing_structures.map((structure, index) => (
                        <li key={index} style={{ color: '#dc3545' }}>{structure}</li>
                      ))}
                    </ul>
                  </div>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <strong>Choose how to proceed:</strong>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {structureChoiceInfo.options.map((option) => (
                      <div key={option.id} style={{ padding: '0.75rem', border: '1px solid #e9ecef', borderRadius: '4px', background: '#f8f9fa' }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                          {option.title}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>
                          {option.description}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                  <button 
                    onClick={() => {
                      setShowStructureChoice(false);
                      setStructureChoiceInfo(null);
                      setPendingSampleEssayRequest(null);
                    }} 
                    style={{ padding: '0.45rem 0.9rem', background: '#e0e0e0', border: '1px solid #ccc', borderRadius: 4, cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={() => handleStructureChoice(false)} 
                    style={{ padding: '0.45rem 0.9rem', background: '#6c757d', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                  >
                    Use Flowchart Structure
                  </button>
                  <button 
                    onClick={() => handleStructureChoice(true)} 
                    style={{ padding: '0.45rem 0.9rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                  >
                    Use Standard Structure
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Stage transition toast removed */}
          {(isExtractingDeplot || isPreparingTaskImage) && currentStage !== 'planning' && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2500 }}>
              <div style={{ background: '#fff', padding: '1.5rem 1.25rem 1.25rem', borderRadius: 8, width: 320, boxShadow: '0 6px 20px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', gap: '0.9rem', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: '1.05rem' }}>
                  {taskPreparationPhase === 'detecting' ? 'Detecting Image...' : 'Analyzing Image...'}
                </h3>
                <div style={{ fontSize: '0.85rem', color: '#444', textAlign: 'center', lineHeight: 1.4 }}>
                  {taskPreparationPhase === 'detecting'
                    ? 'Detecting IELTS task type...'
                    : 'Extracting chart data with DePlot. The first run can take one to three minutes; keep this page open.'}
                </div>
                <div style={{ width: '100%', height: 6, background: '#e5e5e5', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: '65%', height: '100%', background: 'linear-gradient(90deg,#007bff,#5a9bff)', animation: 'deplot-bar 1.2s infinite alternate' }} />
                </div>
                <style>{`@keyframes deplot-bar { from { width: 20%; } to { width: 85%; } }`}</style>
              </div>
            </div>
          )}
          {showImageRequired && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2100 }}>
              <div style={{ background: '#fff', padding: '1.4rem 1.3rem', borderRadius: 8, width: 340, maxWidth: '90%', boxShadow: '0 4px 14px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.05rem' }}>Image Required</h3>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>
                  Please upload the original task image before moving to the next stage.
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button onClick={() => setShowImageRequired(false)} style={{ padding: '0.45rem 0.9rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>OK</button>
                </div>
              </div>
            </div>
          )}
          {showSaveReminder && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2100 }}>
              <div style={{ background: '#fff', padding: '1.4rem 1.3rem', borderRadius: 8, width: 340, maxWidth: '90%', boxShadow: '0 4px 14px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.05rem' }}>Unsaved Changes</h3>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>
                  You have unsaved changes in your text. Do you want to continue to the next stage?
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                  <button onClick={handleSaveReminderCancel} style={{ padding: '0.45rem 0.9rem', background: '#e0e0e0', border: '1px solid #ccc', borderRadius: 4, cursor: 'pointer' }}>Cancel</button>
                  <button onClick={handleSaveReminderConfirm} style={{ padding: '0.45rem 0.9rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Continue</button>
                </div>
              </div>
            </div>
          )}
          <div className="workspace" style={{ display: "flex", flexGrow: 1, width: "100%" }}>
            <div
              className="workspace-left"
              style={{
                flexBasis: `${leftWidth}%`,
                backgroundColor: "#f0f0f0",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div
                className="workspace-panel source-panel"
                style={{
                  // If in planning stage, occupy full height to hide writing area
                  flexBasis: currentStage === 'planning' ? '100%' : `${upperHeight}%`,
                  borderBottom: "1px solid #ccc",
                  padding: "1rem",
                  boxSizing: "border-box",
                  display: "flex",
                  flexDirection: "column",
                  // Allow inner flex children (image area) to shrink properly when resizing
                  // Without this, the image container may overflow and not scale as expected
                  minHeight: 0,
                }}
              >
                <div className="panel-heading">
                  <div>
                    <span className="panel-eyebrow">Source material</span>
                    <h2>Task image</h2>
                  </div>
                  {imagePreview && <span className="status-pill">Ready</span>}
                </div>
                {deplotError && currentStage === 'planning' && (
                  <div style={{ fontSize: '0.7rem', color: '#c00', marginBottom: '0.4rem' }}>{deplotError}</div>
                )}
                
                {/* Chart type selector: only visible during planning stage */}
                {currentStage === 'planning' && (
                  <div className="chart-type-field" style={{ marginBottom: "1rem" }}>
                    <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>
                      Chart Type:
                    </label>
                    <select
                      value={selectedChartType}
                      onChange={(e) => {
                        const nextType = e.target.value;
                        setSelectedChartType(nextType);
                        setChartUrl(null);
                        setChartData(null);
                        setDeplotError("");
                        setTaskDetection(null);
                        setResolvedChartType(null);
                        setIsPreparingTaskImage(false);
                        setTaskPreparationPhase("");
                        taskImagePreparationRef.current = {
                          seq: taskImagePreparationRef.current.seq + 1,
                          promise: null,
                          key: null,
                        };
                        deplotTaskRef.current = {
                          seq: deplotTaskRef.current.seq + 1,
                          promise: null,
                          key: null,
                        };
                        setDeplotText("");
                        setIsExtractingDeplot(false);
                        if (uploadedImage) {
                          prepareUploadedTaskImage(uploadedImage, nextType).catch(() => {});
                        }
                      }}
                      style={{
                        padding: "0.5rem",
                        borderRadius: "4px",
                        border: "1px solid #ccc",
                        fontSize: "1rem",
                        width: "100%",
                        maxWidth: "200px"
                      }}
                    >
                      <option value="auto">Auto Detect</option>
                      <option value="bar">Bar Chart</option>
                      <option value="line">Line Chart</option>
                      <option value="area">Area Chart</option>
                      <option value="pie">Pie Chart</option>
                      <option value="map">Map Task</option>
                      <option value="process">Process Diagram</option>
                    </select>
                    {isPreparingTaskImage && (
                      <div style={{ marginTop: '0.4rem', fontSize: '0.72rem', color: '#444' }}>
                        {taskPreparationPhase === 'detecting'
                          ? 'Detecting IELTS task type...'
                          : taskPreparationPhase === 'deplot'
                          ? 'Extracting chart data with DePlot...'
                          : 'Preparing task image...'}
                      </div>
                    )}
                    {selectedChartType === 'auto' && taskDetection && !taskDetection.needs_confirmation && KNOWN_TASK_TYPES.has(taskDetection.task_type) && (
                      <div style={{ marginTop: '0.4rem', fontSize: '0.72rem', color: '#166534' }}>
                        Auto Detect: {taskTypeLabel(taskDetection.task_type)} ({Math.round(Number(taskDetection.confidence || 0) * 100)}% confidence)
                      </div>
                    )}
                  </div>
                )}
                
                {!imagePreview ? (
                  <div className="upload-dropzone" style={{
                    border: "2px dashed #ccc",
                    borderRadius: "8px",
                    padding: "2rem",
                    textAlign: "center",
                    backgroundColor: "#f9f9f9",
                    flexGrow: 1,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    alignItems: "center"
                  }}>
                    <div className="upload-icon" style={{ fontSize: "3rem", color: "#ccc", marginBottom: "1rem" }}>
                      <Upload size={24} />
                      📷
                    </div>
                    <p style={{ margin: "0 0 1rem 0", color: "#666" }}>
                      Click or drag to upload image
                    </p>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageUpload}
                      style={{ display: "none" }}
                      id="image-upload"
                    />
                    <label
                      className="upload-button"
                      htmlFor="image-upload"
                      style={{
                        padding: "0.5rem 1rem",
                        backgroundColor: "#007bff",
                        color: "white",
                        borderRadius: "4px",
                        cursor: "pointer",
                        border: "none"
                      }}
                    >
                      Choose Image
                    </label>
                    <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.8rem", color: "#999" }}>
                      Supports JPG, PNG, GIF formats, max 5MB
                    </p>
                  </div>
                ) : (
                  <div className="image-preview-shell" style={{ flex: '1 1 auto', display: "flex", flexDirection: "column", minHeight: 0 }}>
                    <div className="image-preview" style={{
                      position: "relative",
                      flex: '1 1 auto',
                      // Match outer pane background
                      backgroundColor: "#f0f0f0",
                      borderRadius: "8px",
                      overflow: "hidden",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      // Ensures container itself can shrink with parent without forcing intrinsic minimums
                      minHeight: 0,
                      width: '100%'
                    }}>
                      <img
                        src={imagePreview}
                        alt="Uploaded chart"
                        style={{
                          width: "100%",
                          height: "100%",
                          objectFit: "contain",
                          // Smooth resizing
                          transition: 'width 0.15s ease, height 0.15s ease',
                          // Prevent image from capturing pointer events (helps with future overlays)
                          pointerEvents: 'none'
                        }}
                      />
                      {stageIndex === 0 && (
                        <button
                          className="icon-button image-remove-button"
                          onClick={handleRemoveImage}
                          style={{
                            position: "absolute",
                            top: "0.55rem",
                            right: "0.55rem",
                            backgroundColor: "rgba(0,0,0,0.72)",
                            color: "white",
                            border: "none",
                            borderRadius: "50%",
                            width: "2rem",
                            height: "2rem",
                            cursor: "pointer",
                            fontSize: "1.25rem",
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            lineHeight: 1,
                            padding: 0
                          }}
                          title="Delete image (removable only in planning stage)"
                        >
                          <X size={16} />
                          ×
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
              {currentStage !== 'planning' && (
                <>
                  <div
                    className="panel-resizer panel-resizer--horizontal"
                    style={{
                      height: "5px",
                      cursor: "row-resize",
                      backgroundColor: "#ccc",
                    }}
                    onMouseDown={handleMouseDownHorizontal}
                  ></div>
                  <div
                    className="workspace-panel writing-panel"
                    style={{
                      flexBasis: `${100 - upperHeight}%`,
                      padding: "1rem",
                      backgroundColor: "#f0f0f0",
                      boxSizing: "border-box",
                      display: "flex",
                      flexDirection: "column",
                      // 允许内部可滚动区域正确收缩
                      minHeight: 0,
                      overflow: 'auto'
                    }}
                  >
                    <div className="panel-heading writing-heading">
                      <div>
                        <span className="panel-eyebrow">{currentStage} stage</span>
                        <h2>Your report</h2>
                      </div>
                      <span className="word-count">{text.trim() ? `${text.trim().split(/\s+/).length} words` : '0 words'}</span>
                    </div>
                    {/* 增加分析文本按钮 */}
                    <div
                      className="editor-surface"
                      style={{
                        height: '300px',
                        overflow: 'auto',
                        borderWidth: '2px',
                        borderStyle: 'solid',
                        borderColor: '#c6c6c6',
                        transition: 'border-color .18s ease, box-shadow .18s ease',
                        borderRadius: 6,
                        background: '#f0f0f0'
                      }}
                    >
                      <CmEditor
                        ref={editorRef}
                        value={text}
                        onChange={setText}
                        placeholder="Start writing or click the Flowchart on the right to plan structure..."
                        style={{ height: '100%' }}
                      />
                    </div>
                    <div className="writing-toolbar" style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem', marginTop: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                      {nextSentenceError && (
                        <span style={{ color: '#c00', fontSize: '0.75rem', marginRight: 'auto' }}>{nextSentenceError}</span>
                      )}
                      {currentStage !== 'revision' && (
                        <button
                          onClick={handleUndoAddition}
                          disabled={!lastAddition}
                          style={{
                            padding: '0.5rem 0.9rem',
                            background: !lastAddition ? '#bbb' : '#ffc107',
                            color: '#272300',
                            border: 'none',
                            borderRadius: 4,
                            cursor: !lastAddition ? 'not-allowed' : 'pointer',
                            fontSize: '0.75rem',
                            fontWeight: 500
                          }}
                          title="Undo last AI sentence"
                        >
                          <RotateCcw size={14} /> Undo
                        </button>
                      )}
                      {currentStage !== 'revision' && (
                        <select
                          value={candidateCount}
                          onChange={e => setCandidateCount(Number(e.target.value))}
                          disabled={isNextSentenceLoading}
                          style={{
                            padding: '0.45rem 0.4rem',
                            background: '#fff',
                            border: '1px solid #bbb',
                            borderRadius: 4,
                            fontSize: '0.75rem',
                            cursor: isNextSentenceLoading ? 'not-allowed' : 'pointer'
                          }}
                          title="Desired number of candidates"
                        >
                          {[1,2,3,4,5,6].map(n => <option key={n} value={n}>{n} candidate{n>1?'s':''}</option>)}
                        </select>
                      )}
                      {currentStage !== 'revision' && (
                        <>
                          <button
                            onClick={handleNextSentence}
                            disabled={isNextSentenceLoading || !uploadedImage || isSpatialTask}
                            style={{
                              padding: '0.5rem 0.9rem',
                              background: isNextSentenceLoading || !uploadedImage || isSpatialTask ? '#888' : '#6f42c1',
                              color: '#fff',
                              border: 'none',
                              borderRadius: 4,
                              cursor: isNextSentenceLoading || !uploadedImage || isSpatialTask ? 'not-allowed' : 'pointer',
                              fontSize: '0.85rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.3rem'
                            }}
                            title={isSpatialTask ? 'Requires a vision-language model for spatial tasks' : 'AI suggest the next sentence'}
                          >
                            <Sparkles size={14} />
                            {isNextSentenceLoading ? 'Thinking...' : 'Next Sentence'}
                          </button>
                          <button
                            onClick={handleGenerateSampleEssay}
                            disabled={isSampleEssayLoading || !uploadedImage}
                            style={{
                              padding: '0.5rem 0.9rem',
                              background: isSampleEssayLoading || !uploadedImage ? '#888' : '#20c997',
                              color: '#fff',
                              border: 'none',
                              borderRadius: 4,
                              cursor: isSampleEssayLoading || !uploadedImage ? 'not-allowed' : 'pointer',
                              fontSize: '0.85rem'
                            }}
                            title="Generate a full sample essay from the original image (overwrites current text)"
                          >
                            <FileText size={14} />
                            {isSampleEssayLoading ? 'Thinking...' : 'Sample Essay'}
                          </button>
                        </>
                      )}
                      <button
                        onClick={runStructureAnalyze}
                        disabled={mappingStatus === 'loading' || !uploadedImage || !flowchartData?.nodes?.length}
                        style={{
                          padding: '0.5rem 0.9rem',
                          background: mappingStatus === 'loading' || !uploadedImage || !flowchartData?.nodes?.length ? '#888' : '#17a2b8',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 4,
                          cursor: mappingStatus === 'loading' || !uploadedImage || !flowchartData?.nodes?.length ? 'not-allowed' : 'pointer',
                          fontSize: '0.85rem'
                        }}
                        title="Analyze structure & map sentences"
                      >
                        <GitBranch size={14} />
                        {mappingStatus === 'loading' ? 'Analyzing structure...' : 'Structure Analyze'}
                      </button>
                      {currentStage === 'revision' && (
                        <button
                          onClick={handleAnalyzeText}
                          disabled={isAnalyzing}
                          style={{
                            padding: '0.5rem 0.9rem',
                            backgroundColor: isAnalyzing ? '#888' : '#007bff',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                            fontSize: '0.85rem'
                          }}
                        >
                          <BarChart3 size={14} />
                          {isAnalyzing ? 'Analyzing...' : 'Analyze Text'}
                        </button>
                      )}
                      { /* Hide analyze button in planning & drafting by not rendering it elsewhere; alternative approach would remove entirely. */ }
                    </div>
                    {SHOW_DEBUG && nextSentenceResult?.debug && (
                      <pre style={{ marginTop: '0.5rem', maxHeight: 120, overflow: 'auto', background: '#fafafa', padding: '0.5rem', fontSize: 11, border: '1px solid #eee' }}>{JSON.stringify(nextSentenceResult.debug, null, 2)}</pre>
                    )}
                    {SHOW_DEBUG && parseMode === 'fallback-split' && (
                      <div style={{ marginTop: 4, fontSize: 11, color: '#b45309', background: '#fff8e1', padding: '4px 6px', border: '1px solid #f0d48a', borderRadius: 4 }}>
                        Model did not return JSON; fallback line-parse mode used.
                      </div>
                    )}
                    {/* Removed Added notification box */}
                    {/* {additionVisible && lastAddition && ( ... )} */}
                  </div>
                </>
              )}
            </div>
            <div
              className="panel-resizer panel-resizer--vertical"
              style={{
                width: "5px",
                cursor: "col-resize",
                backgroundColor: "#ccc",
              }}
              onMouseDown={handleMouseDownVertical}
            ></div>
            <div
              className={`workspace-right ${rightContent === 'Flowchart' ? 'is-flowchart' : ''}`}
              style={{
                flexBasis: `${100 - leftWidth}%`,
                backgroundColor: "#e0e0e0",
                // When editing Flowchart we hide outer scrollbars and let inner canvas manage its own scrolling
                overflow: rightContent === 'Flowchart' ? 'hidden' : 'auto',
                padding: "1rem",
                boxSizing: "border-box",
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div className="right-pane-heading">
                <div>
                  <span className="panel-eyebrow">Learning workspace</span>
                  <h2>Feedback</h2>
                </div>
              </div>
              <div className="view-tabs" style={{ display: "flex", gap: "1rem", marginBottom: "1rem", flexShrink: 0 }}>
                {(currentStage === 'planning' || currentStage === 'drafting') && (
                  <button
                    className={rightContent === 'Flowchart' ? 'is-active' : ''}
                    onClick={() => setRightContent('Flowchart')}
                    style={{
                      padding: '0.5rem 1rem',
                      cursor: 'pointer',
                      backgroundColor: rightContent === 'Flowchart' ? '#6c757d' : '#ffffff',
                      color: rightContent === 'Flowchart' ? '#ffffff' : '#000000',
                      border: '1px solid #dee2e6',
                      borderRadius: '4px'
                    }}
                  >
                    <GitBranch size={14} /> Structure
                  </button>
                )}
                {currentStage === 'revision' && (
                  <>
                    <button
                      className={rightContent === 'Flowchart' ? 'is-active' : ''}
                      onClick={() => setRightContent('Flowchart')}
                      style={{
                        padding: '0.5rem 1rem',
                        cursor: 'pointer',
                        backgroundColor: rightContent === 'Flowchart' ? '#6c757d' : '#ffffff',
                        color: rightContent === 'Flowchart' ? '#ffffff' : '#000000',
                        border: '1px solid #dee2e6',
                        borderRadius: '4px'
                      }}
                    >
                      <GitBranch size={14} /> Structure
                    </button>
                    <button
                      className={rightContent === 'Visual Feedback' ? 'is-active' : ''}
                      onClick={() => setRightContent('Visual Feedback')}
                      style={{
                        padding: '0.5rem 1rem',
                        cursor: 'pointer',
                        backgroundColor: rightContent === 'Visual Feedback' ? '#6c757d' : '#ffffff',
                        color: rightContent === 'Visual Feedback' ? '#ffffff' : '#000000',
                        border: '1px solid #dee2e6',
                        borderRadius: '4px'
                      }}
                    >
                      <BarChart3 size={14} /> Visual feedback
                    </button>
                    <button
                      className={rightContent === 'Revision Suggestions' ? 'is-active' : ''}
                      onClick={() => setRightContent('Revision Suggestions')}
                      style={{
                        padding: '0.5rem 1rem',
                        cursor: 'pointer',
                        backgroundColor: rightContent === 'Revision Suggestions' ? '#6c757d' : '#ffffff',
                        color: rightContent === 'Revision Suggestions' ? '#ffffff' : '#000000',
                        border: '1px solid #dee2e6',
                        borderRadius: '4px'
                      }}
                    >
                      <FileText size={14} /> Revision
                    </button>
                  </>
                )}
              </div>
              {/* 修改5 */}
              {analysisError && (
                <div style={{ 
                  padding: "1rem", 
                  backgroundColor: "#f8d7da", 
                  color: "#721c24", 
                  border: "1px solid #f5c6cb",
                  borderRadius: "4px",
                  marginBottom: "1rem"
                }}>
                  {analysisError}
                </div>
              )}
              
              {rightContent === "Flowchart" && (currentStage === 'planning' || currentStage === 'drafting' || currentStage === 'revision') && (
                <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                  <div style={{ marginBottom: '0.5rem', fontSize: '0.7rem', color: '#333', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <span>
                      Mapping Status: {mappingStatus === 'idle' && '(Not analyzed)'}
                      {mappingStatus === 'loading' && 'Analyzing structure...'}
                      {mappingStatus === 'ok' && 'Paragraph and sentence mapping established'}
                      {mappingStatus === 'missing' && `Missing ${missingNodes.length} structural node(s)`}
                      {mappingStatus === 'error' && 'Mapping failed'}
                    </span>
                    {mappingStatus === 'missing' && missingNodes.length > 0 && (
                      <span style={{ color: '#c00' }}>Please fill missing node content then click Structure Analyze again</span>
                    )}
                  </div>
                  {structureFeedback && mappingStatus !== 'loading' && (
                    <div style={{
                      marginBottom: '0.5rem',
                      padding: '0.45rem 0.6rem',
                      borderLeft: `3px solid ${structureFeedback.is_complete ? '#247047' : '#b45309'}`,
                      background: structureFeedback.is_complete ? '#f0fdf4' : '#fff7ed',
                      fontSize: '0.7rem',
                      lineHeight: 1.35,
                    }}>
                      <strong>{structureFeedback.summary}</strong>
                      {structureFeedback.suggestions?.length > 0 && (
                        <div style={{ marginTop: '0.2rem' }}>
                          {structureFeedback.suggestions.join(' ')}
                        </div>
                      )}
                    </div>
                  )}
                  <div style={{ flex: 1, minHeight: 0 }}>
                    <Flowchart
                      imageReady={!!imagePreview}
                      onFlowchartChange={setFlowchartData}
                      onNodeClick={currentStage === 'planning' ? null : handleNodeClickHighlight}
                      missingNodeIds={new Set(missingNodes.map(m => m.id))}
                      nodeSentenceCounts={nodeToSentenceIndices}
                      nodeParagraphCounts={nodeToParagraphIndices}
                      readOnly={currentStage === 'revision'}
                      currentStage={currentStage}
                    />
                  </div>
                </div>
              )}
              
              {rightContent === "Visual Feedback" && currentStage === 'revision' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {!chartUrl && (
                    <p style={{ margin: 0 }}>Click the "Analyze Text" button to generate visual feedback (chart + structural review).</p>
                  )}
                  {chartUrl && (
                    <div style={{ background: '#fff', padding: '0.75rem', border: '1px solid #ddd', borderRadius: 6 }}>
                      <strong style={{ fontSize: '0.9rem' }}>Generated Chart</strong>
                      <div style={{ marginTop: '0.5rem', display: 'flex', justifyContent: 'center' }}>
                        <img src={chartUrl} alt="Generated feedback chart" style={{ maxWidth: '100%', maxHeight: 300, objectFit: 'contain' }} />
                      </div>
                      <ChartFeedbackDetails chartData={chartData} />
                    </div>
                  )}
                  {/* Chart Data (debug) block removed */}
                </div>
              )}
              
              {rightContent === "Revision Suggestions" && currentStage === 'revision' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', flex: 1, minHeight: 0 }}>
                  {!reviewSuggestions.length && !revisionReview && (
                    <p style={{ margin: 0 }}>Click the "Analyze Text" button to get revision review (vocabulary / grammar / coherence).</p>
                  )}
                  {/* Overall Review moved to bottom */}
                  {reviewSuggestions.length > 0 && (() => {
                    // Group by category
                    const groups = reviewSuggestions.reduce((acc, s) => {
                      const cat = s.category || 'other';
                      (acc[cat] ||= []).push(s);
                      return acc;
                    }, {});
                    // Remove 'overall' category suggestions from grouped display
                    delete groups['overall'];
                    const order = ['vocabulary','grammar','coherence'];
                    const sortedCats = [...order.filter(c=>groups[c]), ...Object.keys(groups).filter(c=>!order.includes(c))];
                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', overflowY: 'auto', minHeight: 0 }}>
                        {sortedCats.map(cat => (
                          <div key={cat} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'capitalize' }}>{cat}</span>
                              <span style={{ fontSize: '0.6rem', color: '#666' }}>({groups[cat].length})</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                              {groups[cat].map(sug => {
                                const active = sug.id === activeSuggestionId;
                                const disabled = sug.applied;
                                const range = sug.range || (Array.isArray(sug.ranges) && sug.ranges[0]);
                                return (
                                  <div
                                    key={sug.id}
                                    onClick={() => {
                                      if (!range || !editorRef.current) return;
                                      const becomingActive = sug.id !== activeSuggestionId;
                                      setActiveSuggestionId(becomingActive ? sug.id : null);
                                      editorRef.current.clearHighlights();
                                      if (becomingActive) {
                                        // 使用持久高亮（false）确保不会 3.5s 后消失
                                        editorRef.current.highlightRange(range.start, range.end, false);
                                      }
                                    }}
                                    style={{
                                      border: '1px solid ' + (active ? '#495057' : '#ddd'),
                                      background: disabled ? '#f1f3f5' : (active ? '#e2e3e5' : '#fff'),
                                      padding: '0.65rem 0.75rem',
                                      borderRadius: 8,
                                      display: 'flex',
                                      flexDirection: 'column',
                                      gap: '0.4rem',
                                      fontSize: '0.75rem',
                                      position: 'relative',
                                      cursor: range ? 'pointer' : 'default',
                                      transition: 'background .15s, border-color .15s'
                                    }}
                                  >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ fontWeight: 600, fontSize: '0.7rem', textTransform: 'capitalize' }}>{sug.severity}</span>
                                      <div style={{ display: 'flex', gap: '0.45rem', alignItems: 'center' }}>
                                        <button
                                          disabled={disabled || !sug.replacement}
                                          onClick={(e) => { e.stopPropagation(); applySuggestion(sug); }}
                                          style={{
                                            border: '1px solid ' + (disabled ? '#ccc' : '#146c43'),
                                            background: disabled ? '#e9ecef' : '#198754',
                                            color: disabled ? '#666' : '#fff',
                                            fontSize: '0.7rem',
                                            padding: '0.35rem 0.8rem',
                                            borderRadius: 6,
                                            cursor: disabled ? 'not-allowed' : 'pointer',
                                            fontWeight: 600,
                                            boxShadow: disabled ? 'none' : '0 1px 2px rgba(0,0,0,0.15)'
                                          }}
                                        >{disabled ? 'Applied' : 'Apply'}</button>
                                      </div>
                                    </div>
                                    <div style={{ lineHeight: 1.3 }}>{sug.message}</div>
                                    {sug.excerpt && (
                                      <div style={{ fontSize: '0.62rem', color: '#555', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                        <span style={{ fontWeight: 600 }}>Original:</span>
                                        <code style={{ background: '#f8f9fa', padding: '2px 4px', borderRadius: 4 }}>{sug.excerpt}</code>
                                      </div>
                                    )}
                                    {sug.replacement && (
                                      <div style={{ fontSize: '0.62rem', color: '#555', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                        <span style={{ fontWeight: 600 }}>Replacement:</span>
                                        <code style={{ background: '#fff3cd', padding: '2px 4px', borderRadius: 4 }}>{sug.replacement}</code>
                                      </div>
                                    )}
                                    {sug.applyError && (
                                      <div style={{ fontSize: '0.55rem', color: '#c92a2a' }}>{sug.applyError}</div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                        {/* Overall review card placed after grouped suggestions */}
                        {revisionReview && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', background: '#f7f7f7', padding: '0.75rem 0.85rem', border: '1px solid #ddd', borderRadius: 6 }}>
                            <strong style={{ fontSize: '0.95rem' }}>Overall Review</strong>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', fontSize: '0.75rem' }}>
                              {['vocabulary','grammar','coherence'].map(cat => (
                                <span key={cat} style={{ background: '#fff', border: '1px solid #ccc', borderRadius: 4, padding: '0.3rem 0.4rem' }}>
                                  {cat}: {revisionReview[cat]?.score ?? '-'}
                                </span>
                              ))}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#444' }}>{revisionReview.summary}</div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>
        </>
        </ErrorBoundary>
      ) : (
        <>
          <Login onLogin={handleLogin} passwordRequired={passwordRequired} />
        </>
      )}
    </main>
    {isLoggedIn && currentStage !== 'revision' && showCandidatePanel && aiCandidates.length > 0 && (
      <div className="candidate-panel" style={{ position: 'fixed', bottom: 16, right: 16, width: 380, maxWidth: '90vw', background: '#fff', border: '1px solid #ddd', boxShadow: '0 4px 18px rgba(0,0,0,0.15)', borderRadius: 8, zIndex: 4000, display: 'flex', flexDirection: 'column', maxHeight: '60vh' }}>
        <div className="candidate-panel-header" style={{ padding: '0.65rem 0.85rem', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <strong style={{ fontSize: 14 }}>Candidate Next Sentences ({aiCandidates.length})</strong>
          <button className="icon-button" aria-label="Close suggestions" onClick={() => setShowCandidatePanel(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, lineHeight: 1 }}><X size={16} /></button>
        </div>
        <div className="candidate-list" style={{ overflowY: 'auto', padding: '0.5rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
          {aiCandidates.map((c, idx) => (
            <button key={idx} onClick={() => insertCandidate(c)} style={{
              textAlign: 'left',
              background: '#f8f9fa',
              border: '1px solid #e2e3e5',
              borderRadius: 6,
              padding: '0.55rem 0.6rem',
              fontSize: 13,
              lineHeight: 1.4,
              cursor: 'pointer',
              transition: 'background .15s',
              whiteSpace: 'normal'
            }}
            onMouseEnter={(e)=> e.currentTarget.style.background='#eef2ff'}
            onMouseLeave={(e)=> e.currentTarget.style.background='#f8f9fa'}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="candidate-panel-footer" style={{ borderTop: '1px solid #eee', padding: '0.45rem 0.7rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: '#666' }}>Shift+click "Next Sentence" to immediately use the first candidate</span>
          <button onClick={() => { if (aiCandidates[0]) insertCandidate(aiCandidates[0]); }} style={{ background: '#6f42c1', color: '#fff', border: 'none', borderRadius: 4, padding: '0.45rem 0.8rem', fontSize: 12, cursor: 'pointer' }}>Use First</button>
        </div>
      </div>
    )}
    </>
  );
}
