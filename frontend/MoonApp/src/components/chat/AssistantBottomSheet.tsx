import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Dimensions,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Ionicons';
import { WebView } from 'react-native-webview';
import { COLORS } from '../../constants/colors';
import { useSTT } from '../../hooks/useSTT';
import { sendConversation } from '../../services/navigationApi';
import { speak as ttsSpeak, stop as ttsStop } from '../../services/ttsService';
import { useRouteStore } from '../../stores/useRouteStore';
import type { DecisionPoint } from '../../types/route';
import { buildPanoramaHtml, getPrimaryPan } from '../../utils/panoramaUtils';
import ChatBubble from './ChatBubble';
import TypingIndicator from './TypingIndicator';
import VoiceButton from './VoiceButton';

interface Props {
  visible: boolean;
  onClose: () => void;
  routeId: string | null;
  currentDpId: string | null;
  // 잠금화면 위젯 "질문하기" 트리거. 카운터 값이 증가할 때마다 STT 자동 시작.
  // 시트가 이미 열려있는 상태에서도 카운터 증가만으로 재트리거 가능.
  autoStartCounter?: number;
  // STT isListening 상태 변화를 부모(NavigationScreen)에 보고. 위젯 상태 갱신용.
  onListeningChange?: (listening: boolean) => void;
}

interface PanoramaPayload {
  dpId: string;
  lat: number;
  lng: number;
  pan: number;
  landmarkName: string | null;
  landmarkLat: number | null;
  landmarkLng: number | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  panorama?: PanoramaPayload;
}

const SCREEN_HEIGHT = Dimensions.get('window').height;
const SHEET_HEIGHT = Math.round(SCREEN_HEIGHT * 0.6);
const INITIAL_TEXT = '무엇을 도와드릴까요?';
const TYPING_CHAR_DELAY_MS = 45;
// 타이핑 인디케이터 최소 노출 시간. mock 응답이 즉시 와도 자연스러운
// "AI가 생각 중" 인상을 주기 위함. 실제 API가 더 걸리면 자연히 그만큼 유지됨.
const MIN_INDICATOR_MS = 2000;

function buildPanoramaPayload(dp: DecisionPoint): PanoramaPayload | null {
  if (!dp.panoramaRequest) { return null; }
  const pan = getPrimaryPan(dp);
  if (pan === null) { return null; }
  const lm = dp.selectedLandmark;
  return {
    dpId: dp.dpId,
    lat: dp.panoramaRequest.location.latitude,
    lng: dp.panoramaRequest.location.longitude,
    pan,
    landmarkName: lm?.name ?? null,
    landmarkLat: lm?.location?.latitude ?? null,
    landmarkLng: lm?.location?.longitude ?? null,
  };
}

export default function AssistantBottomSheet({
  visible,
  onClose,
  routeId,
  currentDpId,
  autoStartCounter,
  onListeningChange,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [inputText, setInputText] = useState('');
  const { transcript, isListening, startListening, stopListening, reset } = useSTT();
  const decisionPoints = useRouteStore(s => s.decisionPoints);

  const dpById = useMemo(() => {
    const map = new Map<string, DecisionPoint>();
    decisionPoints.forEach(dp => map.set(dp.dpId, dp));
    return map;
  }, [decisionPoints]);

  const scrollRef = useRef<ScrollView>(null);
  const lastSubmittedRef = useRef<string>('');
  const isProcessingRef = useRef(false);
  const typingTimersRef = useRef<Array<ReturnType<typeof setTimeout>>>([]);

  const clearTypingTimers = useCallback(() => {
    typingTimersRef.current.forEach(clearTimeout);
    typingTimersRef.current = [];
  }, []);

  const typeAssistantMessage = useCallback(
    (id: string, fullText: string, charDelay = TYPING_CHAR_DELAY_MS) => {
      let idx = 0;
      const tick = () => {
        idx += 1;
        if (idx > fullText.length) { return; }
        setMessages(prev =>
          prev.map(m => (m.id === id ? { ...m, text: fullText.slice(0, idx) } : m)),
        );
        if (idx < fullText.length) {
          const t = setTimeout(tick, charDelay);
          typingTimersRef.current.push(t);
        }
      };
      const t = setTimeout(tick, charDelay);
      typingTimersRef.current.push(t);
    },
    [],
  );

  // Open/close lifecycle
  useEffect(() => {
    if (visible) {
      console.log('[Assistant] sheet opened');
      clearTypingTimers();
      const initId = `init-${Date.now()}`;
      setMessages([{ id: initId, role: 'assistant', text: '' }]);
      typeAssistantMessage(initId, INITIAL_TEXT);
    } else {
      console.log('[Assistant] sheet closed');
      clearTypingTimers();
      ttsStop();
      stopListening().catch(() => {});
      setMessages([]);
      setIsProcessing(false);
      setInputText('');
      lastSubmittedRef.current = '';
      reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTypingTimers();
    };
  }, [clearTypingTimers]);

  // 잠금화면 위젯 트리거: autoStartCounter 증가 시 STT 자동 시작.
  // visible이 false → true로 전환되며 시트가 열리는 첫 렌더에서는 messages가
  // 비어있을 수 있으므로, 한 틱 양보한 뒤 startListening 호출.
  useEffect(() => {
    if (!autoStartCounter || autoStartCounter <= 0) { return; }
    if (!visible) { return; }
    console.log('[Assistant] autoStartCounter triggered:', autoStartCounter);
    ttsStop();
    const t = setTimeout(() => {
      startListening().catch((e) => console.warn('[Assistant] auto startListening failed', e));
    }, 250);
    return () => clearTimeout(t);
  }, [autoStartCounter, visible, startListening]);

  // isListening 변화를 부모에 알림 (위젯 상태 갱신용)
  useEffect(() => {
    onListeningChange?.(isListening);
  }, [isListening, onListeningChange]);

  const handleAnswer = useCallback(
    async (question: string) => {
      console.log('[Assistant] handleAnswer:', question);
      if (!routeId) {
        const id = `a-${Date.now()}`;
        setMessages(prev => [...prev, { id, role: 'assistant', text: '' }]);
        typeAssistantMessage(id, '경로 정보가 없어요. 다시 시도해주세요.');
        return;
      }
      isProcessingRef.current = true;
      setIsProcessing(true);
      const startTime = Date.now();
      // 인디케이터 최소 노출시간 보장용 pending 처리. try/catch 어느 경로든
      // finally에서 elapsed를 보고 부족하면 setTimeout으로 마저 채운 뒤 해제.
      let pendingResult:
        | { kind: 'ok'; answer: string; panorama?: PanoramaPayload }
        | { kind: 'err' }
        | null = null;
      try {
        const result = await sendConversation(routeId, question, {
          currentDpId: currentDpId ?? undefined,
        });
        const { answer, showPanorama, targetDpId } = result;
        console.log(
          '[Assistant] got answer:',
          answer.substring(0, 40),
          'showPanorama:',
          showPanorama,
          'targetDpId:',
          targetDpId,
        );

        let panorama: PanoramaPayload | undefined;
        if (showPanorama) {
          const lookupId = targetDpId ?? currentDpId ?? null;
          const dp = lookupId ? dpById.get(lookupId) : undefined;
          if (dp) {
            const payload = buildPanoramaPayload(dp);
            if (payload) { panorama = payload; }
          }
          if (!panorama) {
            console.warn('[Assistant] panorama requested but no DP/pano data', lookupId);
          }
        }

        pendingResult = { kind: 'ok', answer, panorama };
      } catch (e) {
        console.warn('[Assistant] sendConversation failed:', e);
        pendingResult = { kind: 'err' };
      } finally {
        const elapsed = Date.now() - startTime;
        const wait = Math.max(0, MIN_INDICATOR_MS - elapsed);
        const finalize = () => {
          if (pendingResult?.kind === 'ok') {
            const id = `a-${Date.now()}`;
            setMessages(prev => [
              ...prev,
              { id, role: 'assistant', text: '', panorama: pendingResult!.kind === 'ok' ? pendingResult!.panorama : undefined },
            ]);
            ttsStop();
            ttsSpeak(pendingResult.answer);
            typeAssistantMessage(id, pendingResult.answer);
          } else {
            const id = `a-${Date.now()}`;
            setMessages(prev => [...prev, { id, role: 'assistant', text: '' }]);
            typeAssistantMessage(id, '답변을 받지 못했어요. 다시 시도해주세요.');
          }
          isProcessingRef.current = false;
          setIsProcessing(false);
        };
        if (wait > 0) {
          const t = setTimeout(finalize, wait);
          typingTimersRef.current.push(t);
        } else {
          finalize();
        }
      }
    },
    [routeId, currentDpId, typeAssistantMessage, dpById],
  );

  // STT transcript → submit on session end
  useEffect(() => {
    if (!visible) { return; }
    if (isListening) { return; }
    const text = transcript.trim();
    if (text.length === 0) { return; }
    if (text === lastSubmittedRef.current) { return; }
    if (isProcessingRef.current) { return; }
    lastSubmittedRef.current = text;
    console.log('[Assistant] submitting transcript:', text);
    setMessages(prev => [...prev, { id: `u-${Date.now()}`, role: 'user', text }]);
    reset();
    handleAnswer(text);
  }, [visible, isListening, transcript, reset, handleAnswer]);

  const handleMicPress = useCallback(() => {
    console.log('[Assistant] mic press — isListening:', isListening, 'isProcessing:', isProcessing);
    if (isProcessing) { return; }
    if (isListening) {
      stopListening();
    } else {
      ttsStop();
      startListening();
    }
  }, [isListening, isProcessing, startListening, stopListening]);

  const handleSendText = useCallback(() => {
    const text = inputText.trim();
    if (text.length === 0 || isProcessing) { return; }
    console.log('[Assistant] send text:', text);
    setInputText('');
    setMessages(prev => [...prev, { id: `u-${Date.now()}`, role: 'user', text }]);
    handleAnswer(text);
  }, [inputText, isProcessing, handleAnswer]);

  const statusText = isProcessing
    ? '답변을 준비하고 있어요...'
    : isListening
      ? '듣고 있어요...'
      : '마이크를 눌러 질문하세요';

  const canSendText = inputText.trim().length > 0 && !isProcessing;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <KeyboardAvoidingView
        style={styles.backdrop}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Pressable style={styles.backdropPressable} onPress={onClose} />
        <SafeAreaView style={styles.sheet} edges={['bottom']}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <Icon name="sparkles" size={16} color={COLORS.primary} />
              <Text style={styles.headerTitle}>어시스턴트</Text>
            </View>
            <TouchableOpacity
              onPress={onClose}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Icon name="close" size={22} color={COLORS.text} />
            </TouchableOpacity>
          </View>

          {/* Chat area */}
          <View style={styles.chatBox}>
            <ScrollView
              ref={scrollRef}
              style={styles.chatScroll}
              showsVerticalScrollIndicator
              nestedScrollEnabled
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={styles.chatContent}
              onContentSizeChange={() =>
                scrollRef.current?.scrollToEnd({ animated: true })
              }
            >
              {messages.map(m => (
                <View key={m.id}>
                  {m.panorama && (
                    <View style={styles.panoramaBox}>
                      <WebView
                        key={`assistant-pano-${m.id}`}
                        source={{
                          html: buildPanoramaHtml(
                            m.panorama.lat,
                            m.panorama.lng,
                            m.panorama.pan,
                            m.panorama.landmarkName,
                            m.panorama.landmarkLat,
                            m.panorama.landmarkLng,
                          ),
                        }}
                        style={styles.panoramaWebview}
                        scrollEnabled={false}
                        nestedScrollEnabled
                        javaScriptEnabled
                        domStorageEnabled
                        originWhitelist={['*']}
                        cacheEnabled={false}
                        incognito
                        androidLayerType="software"
                      />
                    </View>
                  )}
                  <ChatBubble text={m.text} isUser={m.role === 'user'} />
                </View>
              ))}
              {isProcessing && <TypingIndicator />}
            </ScrollView>
          </View>

          {/* Mic area */}
          <View style={styles.micArea}>
            <VoiceButton
              onPress={handleMicPress}
              isListening={isListening}
              size={48}
            />
            <Text style={styles.statusText}>{statusText}</Text>
          </View>

          {/* Text input fallback */}
          <View style={styles.inputRow}>
            <TextInput
              style={styles.textInput}
              value={inputText}
              onChangeText={setInputText}
              placeholder="텍스트로 질문하기"
              placeholderTextColor={COLORS.subtext}
              returnKeyType="send"
              onSubmitEditing={handleSendText}
              editable={!isProcessing}
              blurOnSubmit
            />
            <TouchableOpacity
              style={[styles.sendBtn, !canSendText && styles.sendBtnDisabled]}
              onPress={handleSendText}
              disabled={!canSendText}
              activeOpacity={0.7}
            >
              <Icon name="send" size={18} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'flex-end',
  },
  backdropPressable: {
    flex: 1,
  },
  sheet: {
    height: SHEET_HEIGHT,
    backgroundColor: COLORS.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    elevation: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -3 },
    shadowOpacity: 0.15,
    shadowRadius: 10,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
    paddingBottom: 10,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  headerTitle: {
    fontSize: 15,
    fontWeight: '500',
    color: COLORS.primary,
  },
  chatBox: {
    flex: 1,
    backgroundColor: '#F5F5F7',
    borderRadius: 12,
    padding: 12,
    overflow: 'hidden',
  },
  chatScroll: {
    flex: 1,
  },
  chatContent: {
    flexGrow: 1,
    paddingBottom: 4,
  },
  panoramaBox: {
    width: '100%',
    aspectRatio: 16 / 9,
    borderRadius: 10,
    overflow: 'hidden',
    backgroundColor: '#000',
    marginVertical: 6,
  },
  panoramaWebview: {
    flex: 1,
    backgroundColor: '#000',
  },
  micArea: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 12,
    paddingBottom: 8,
    gap: 6,
  },
  statusText: {
    fontSize: 13,
    color: COLORS.subtext,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingTop: 8,
  },
  textInput: {
    flex: 1,
    height: 40,
    paddingHorizontal: 12,
    backgroundColor: '#F5F5F7',
    borderRadius: 20,
    borderWidth: 0.5,
    borderColor: '#E5E5EA',
    fontSize: 14,
    color: COLORS.text,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: '#C5C5C5',
  },
});
