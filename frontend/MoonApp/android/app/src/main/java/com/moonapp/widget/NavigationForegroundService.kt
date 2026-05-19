package com.moonapp.widget

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.os.Build
import android.os.IBinder
import android.text.SpannableString
import android.text.Spanned
import android.text.style.StyleSpan
import android.util.Log
import androidx.annotation.DrawableRes
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.core.graphics.drawable.IconCompat
import com.moonapp.R

class NavigationForegroundService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> handleStart(intent)
            ACTION_UPDATE -> handleUpdate(intent)
            ACTION_STOP -> handleStop()
            else -> Log.w(TAG, "Unknown action: ${intent?.action}")
        }
        return START_STICKY
    }

    private fun handleStart(intent: Intent) {
        ensureChannel(this)
        val notification = buildNotification(extractState(intent))
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // 잠금화면 위젯 마이크 액션이 STT를 트리거할 수 있도록 MICROPHONE 타입도 함께 선언.
            // (API 34+ 부터는 마이크 사용 시 명시적으로 type=microphone 요구됨)
            val fgsType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION or
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
            } else {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
            }
            ServiceCompat.startForeground(
                this,
                NOTIFICATION_ID,
                notification,
                fgsType,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun handleUpdate(intent: Intent) {
        val notification = buildNotification(extractState(intent))
        try {
            NotificationManagerCompat.from(this).notify(NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted on Android 13+.
        }
    }

    private fun handleStop() {
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun extractState(intent: Intent): WidgetState = WidgetState(
        label = intent.getStringExtra(EXTRA_LABEL) ?: DEFAULT_LABEL,
        primary = intent.getStringExtra(EXTRA_PRIMARY) ?: DEFAULT_PRIMARY,
        next = intent.getStringExtra(EXTRA_NEXT) ?: DEFAULT_NEXT,
        arrowType = intent.getStringExtra(EXTRA_ARROW_TYPE) ?: DEFAULT_ARROW_TYPE,
        progress = intent.getIntExtra(EXTRA_PROGRESS, DEFAULT_PROGRESS),
        currentIndex = intent.getIntExtra(EXTRA_CURRENT_INDEX, 0),
        totalCount = intent.getIntExtra(EXTRA_TOTAL_COUNT, 0),
        dpTypes = intent.getStringArrayListExtra(EXTRA_DP_TYPES)?.toList() ?: emptyList(),
        isListening = intent.getBooleanExtra(EXTRA_IS_LISTENING, false),
    )

    private fun buildNotification(state: WidgetState): Notification {
        Log.d(
            "NavWidget",
            "idx=${state.currentIndex} total=${state.totalCount} arrow=${state.arrowType} pct=${state.progress}",
        )
        val pct = state.progress.coerceIn(0, 100)
        val title = state.label.ifBlank { DEFAULT_LABEL }
        val chipText = when (state.arrowType) {
            ARROW_WARNING -> "재탐색 중"
            ARROW_ARRIVED -> "도착"
            else -> "$pct%"
        }

        val largeIconRes = when (state.arrowType) {
            ARROW_WARNING -> R.drawable.ic_arrow_warning
            ARROW_ARRIVED -> R.drawable.ic_arrow_arrived
            else -> arrowResForType(state.arrowType)
        }

        val stopIntent = Intent(this, NavigationForegroundService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPending = PendingIntent.getService(
            this,
            0,
            stopIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val micIntent = Intent(this, WidgetMicActionReceiver::class.java).apply {
            action = WidgetMicActionReceiver.ACTION_MIC_TRIGGER
            `package` = packageName
        }
        val micPending = PendingIntent.getBroadcast(
            this,
            1,
            micIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val micLabel = if (state.isListening) MIC_LABEL_LISTENING else MIC_LABEL_IDLE

        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification_small)
            .setLargeIcon(createLargeIconBitmap(largeIconRes))
            .setContentTitle(boldText(title))
            .setContentText(state.primary)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setCategory(NotificationCompat.CATEGORY_NAVIGATION)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setRequestPromotedOngoing(true)
            .setShortCriticalText(chipText)
            .setStyle(buildProgressStyle(state, pct))
            .addAction(
                NotificationCompat.Action.Builder(0, "안내 종료", stopPending).build(),
            )
            .addAction(
                NotificationCompat.Action.Builder(0, micLabel, micPending).build(),
            )

        if (state.next.isNotBlank()) {
            builder.setSubText(state.next)
        }

        return builder.build()
    }

    private fun buildProgressStyle(state: WidgetState, pct: Int): NotificationCompat.ProgressStyle {
        return when (state.arrowType) {
            ARROW_WARNING -> NotificationCompat.ProgressStyle()
                .setStyledByProgress(false)
                .setProgressSegments(
                    listOf(NotificationCompat.ProgressStyle.Segment(100).setColor(PALE_BLUE)),
                )
                .setProgressTrackerIcon(emojiToIcon(TRACKER_EMOJI))
                .setProgress(50)

            ARROW_ARRIVED -> NotificationCompat.ProgressStyle()
                .setStyledByProgress(false)
                .setProgressSegments(
                    listOf(NotificationCompat.ProgressStyle.Segment(100).setColor(MIDNIGHT_BLUE)),
                )
                .setProgressEndIcon(
                    IconCompat.createWithResource(this, R.drawable.ic_arrow_arrived),
                )
                .setProgress(100)

            else -> {
                val segments = if (state.totalCount > 1) {
                    buildDpSegments(state.currentIndex, state.totalCount, state.dpTypes)
                } else {
                    when {
                        pct == 0 -> listOf(
                            NotificationCompat.ProgressStyle.Segment(100).setColor(PALE_BLUE),
                        )
                        pct == 100 -> listOf(
                            NotificationCompat.ProgressStyle.Segment(100).setColor(MIDNIGHT_BLUE),
                        )
                        else -> listOf(
                            NotificationCompat.ProgressStyle.Segment(pct).setColor(MIDNIGHT_BLUE),
                            NotificationCompat.ProgressStyle.Segment(100 - pct).setColor(PALE_BLUE),
                        )
                    }
                }
                NotificationCompat.ProgressStyle()
                    .setStyledByProgress(false)
                    .setProgressSegments(segments)
                    .setProgressTrackerIcon(emojiToIcon(TRACKER_EMOJI))
                    .setProgress(pct)
            }
        }
    }

    private data class DpGroup(val type: String, val count: Int, val startIdx: Int)

    private fun groupDpTypes(dpTypes: List<String>): List<DpGroup> {
        val groups = mutableListOf<DpGroup>()
        var i = 0
        while (i < dpTypes.size) {
            val type = dpTypes[i]
            var j = i
            while (j < dpTypes.size && dpTypes[j] == type) j++
            groups.add(DpGroup(type, j - i, i))
            i = j
        }
        return groups
    }

    private fun colorForGroup(group: DpGroup, currentIndex: Int): Int {
        val groupEnd = group.startIdx + group.count
        val isCurrent = currentIndex in group.startIdx until groupEnd
        val isCompleted = groupEnd <= currentIndex

        return when {
            isCurrent -> ACCENT_GOLD
            isCompleted -> when (group.type) {
                ARROW_LEFT, ARROW_RIGHT -> GOLD
                ARROW_CROSSWALK -> MINT
                ARROW_VERTICAL -> BROWN
                ARROW_ARRIVED -> CORAL
                ARROW_STRAIGHT -> {
                    // 긴 직진 그룹 인접 시각 분리: 그룹 시작 인덱스 짝홀로 미세 변형
                    if (group.startIdx % 2 == 0) MIDNIGHT_BLUE else MIDNIGHT_BLUE_LIGHT
                }
                else -> MIDNIGHT_BLUE
            }
            else -> {
                // 남은 그룹: 연한 톤 (타입 구분 미미)
                if (group.startIdx % 2 == 0) PALE_BLUE else PALE_BLUE_DARK
            }
        }
    }

    private fun buildDpSegments(
        currentIndex: Int,
        totalCount: Int,
        dpTypes: List<String>,
    ): List<NotificationCompat.ProgressStyle.Segment> {
        if (dpTypes.isEmpty() || dpTypes.size != totalCount) {
            // fallback: 단일 segment (정보 없음)
            return listOf(
                NotificationCompat.ProgressStyle.Segment(100).setColor(MIDNIGHT_BLUE),
            )
        }

        val safeTotal = totalCount.coerceAtLeast(1)
        // 그룹화 비활성: 각 DP를 1칸짜리 그룹으로 1:1 매핑.
        // (groupDpTypes는 dead code로 남김 — 추후 다시 그룹 표시 원하면 복원)
        val groups = dpTypes.mapIndexed { i, t -> DpGroup(t, 1, i) }

        // 길이 = (그룹 DP 수 / 전체) * 100, 마지막 그룹에 remainder 흡수
        val baseLengths = groups.map { (it.count * 100) / safeTotal }
        val sumBase = baseLengths.sum()
        val lengths = baseLengths.toMutableList()
        if (lengths.isNotEmpty()) {
            lengths[lengths.size - 1] = lengths.last() + (100 - sumBase)
        }

        Log.d(
            "NavWidget",
            "buildStyle: idx=$currentIndex total=$totalCount dpTypesSize=${dpTypes.size} " +
                "groupCount=${groups.size} groups=${groups.joinToString { "${it.type}x${it.count}" }}",
        )

        return groups.mapIndexed { idx, group ->
            val length = lengths[idx].coerceAtLeast(1)
            NotificationCompat.ProgressStyle.Segment(length)
                .setColor(colorForGroup(group, currentIndex))
        }
    }

    private fun boldText(text: String): CharSequence {
        val spannable = SpannableString(text)
        spannable.setSpan(
            StyleSpan(Typeface.BOLD),
            0,
            text.length,
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
        )
        return spannable
    }

    private fun emojiToIcon(emoji: String, sizeDp: Int = 32): IconCompat {
        val sizePx = (sizeDp * resources.displayMetrics.density).toInt()
        val bitmap = Bitmap.createBitmap(
            sizePx, sizePx, Bitmap.Config.ARGB_8888,
        )
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = sizePx * 0.85f
            textAlign = Paint.Align.CENTER
        }
        val fm = paint.fontMetrics
        val y = sizePx / 2f - (fm.ascent + fm.descent) / 2f
        canvas.drawText(emoji, sizePx / 2f, y, paint)
        return IconCompat.createWithBitmap(bitmap)
    }

    // Step 10: 트래커는 이모지로 교체. 본 함수는 롤백 대비 보존.
    private fun buildTrackerIcon(arrowType: String): IconCompat {
        val size = 96
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        // 흰색 외곽 링 (segment에서 떠 있는 느낌)
        val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            style = Paint.Style.FILL
        }
        canvas.drawCircle(size / 2f, size / 2f, size / 2f, ringPaint)

        // 안쪽 어두운 남색 원
        val innerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = MIDNIGHT_BLUE
            style = Paint.Style.FILL
        }
        canvas.drawCircle(size / 2f, size / 2f, size / 2f - 6f, innerPaint)

        // 가운데 흰색 픽토그램
        val arrowDrawable = ContextCompat.getDrawable(this, arrowResForType(arrowType))!!.mutate()
        arrowDrawable.setTint(Color.WHITE)
        val padding = size / 4
        arrowDrawable.setBounds(padding, padding, size - padding, size - padding)
        arrowDrawable.draw(canvas)

        return IconCompat.createWithBitmap(bitmap)
    }

    private fun createLargeIconBitmap(@DrawableRes resId: Int): Bitmap {
        val size = 192
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        val drawable = ContextCompat.getDrawable(this, resId)!!.mutate()
        drawable.setTint(MIDNIGHT_BLUE)
        drawable.setBounds(0, 0, size, size)
        drawable.draw(canvas)

        return bitmap
    }

    private fun arrowResForType(type: String): Int = when (type) {
        ARROW_LEFT -> R.drawable.ic_arrow_left
        ARROW_RIGHT -> R.drawable.ic_arrow_right
        ARROW_STRAIGHT -> R.drawable.ic_arrow_straight
        ARROW_ARRIVED -> R.drawable.ic_arrow_arrived
        ARROW_WARNING -> R.drawable.ic_arrow_warning
        ARROW_CROSSWALK -> R.drawable.ic_arrow_crosswalk
        ARROW_VERTICAL -> R.drawable.ic_arrow_vertical
        else -> R.drawable.ic_arrow_straight
    }

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        // Lazy 생성: 채널 promote 자격 리셋 방지 + 사용자 커스터마이즈 보존.
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "경로 안내 잠금화면 위젯"
            setShowBadge(false)
            setBypassDnd(true)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        manager.createNotificationChannel(channel)
    }

    private data class WidgetState(
        val label: String,
        val primary: String,
        val next: String,
        val arrowType: String,
        val progress: Int,
        val currentIndex: Int,
        val totalCount: Int,
        val dpTypes: List<String> = emptyList(),
        val isListening: Boolean = false,
    )

    companion object {
        private const val TAG = "NavForegroundSvc"

        const val ACTION_START = "com.moonapp.widget.action.START"
        const val ACTION_UPDATE = "com.moonapp.widget.action.UPDATE"
        const val ACTION_STOP = "com.moonapp.widget.action.STOP"

        const val EXTRA_LABEL = "extra_label"
        const val EXTRA_PRIMARY = "extra_primary"
        const val EXTRA_NEXT = "extra_next"
        const val EXTRA_PROGRESS = "extra_progress"
        const val EXTRA_ARROW_TYPE = "extra_arrow_type"
        const val EXTRA_CURRENT_INDEX = "extra_current_index"
        const val EXTRA_TOTAL_COUNT = "extra_total_count"
        const val EXTRA_DP_TYPES = "extra_dp_types"
        const val EXTRA_IS_LISTENING = "extra_is_listening"

        private const val MIC_LABEL_IDLE = "질문하기"
        private const val MIC_LABEL_LISTENING = "듣는 중"

        const val ARROW_LEFT = "left"
        const val ARROW_RIGHT = "right"
        const val ARROW_STRAIGHT = "straight"
        const val ARROW_ARRIVED = "arrived"
        const val ARROW_WARNING = "warning"
        const val ARROW_CROSSWALK = "crosswalk"
        const val ARROW_VERTICAL = "vertical_move"

        const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "navigation_guide"
        private const val CHANNEL_NAME = "내비게이션 안내"

        private const val DEFAULT_LABEL = "다음 안내"
        private const val DEFAULT_PRIMARY = "조앤조의원 앞에서 우회전하세요"
        private const val DEFAULT_NEXT = "다음 · KB국민은행"
        private const val DEFAULT_PROGRESS = 36
        private const val DEFAULT_ARROW_TYPE = ARROW_RIGHT

        private val MIDNIGHT_BLUE = Color.parseColor("#191970")         // 직진 (메인 남색)
        private val MIDNIGHT_BLUE_LIGHT = Color.parseColor("#2D3A8C")   // 직진 변형 (살짝 밝음)
        private val GOLD = Color.parseColor("#C9A86A")                  // 회전 (좌/우) — 보색 강조
        private val MINT = Color.parseColor("#4ECDC4")                  // 횡단보도 — 시원한 안전 톤
        private val BROWN = Color.parseColor("#B08968")                 // 수직이동 — 실내/계단 느낌
        private val ACCENT_GOLD = Color.parseColor("#F4A261")           // 현재 강조 (따뜻한 골드)
        private val CORAL = Color.parseColor("#E76F51")                 // 도착 (따뜻한 코랄)
        private val PALE_BLUE = Color.parseColor("#C8CBE0")             // 남은 구간 (연한 회보라)
        private val PALE_BLUE_DARK = Color.parseColor("#A0A4C8")        // 남은 변형 (어두운 회보라)

        // 진행률 트래커 이모지 (Pixel API 36에서 Emoji 15.1 완전 지원 확인됨)
        private const val TRACKER_EMOJI = "🚶🏻‍♂️‍➡️"
    }
}
