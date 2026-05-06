package com.moonapp.widget

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import android.widget.RemoteViews
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
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
            ServiceCompat.startForeground(
                this,
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION,
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
    )

    private fun buildNotification(state: WidgetState): Notification {
        val arrowRes = arrowResForType(state.arrowType)
        val progressClamped = state.progress.coerceIn(0, 100)
        val progressText = "$progressClamped%"

        val expandedView = RemoteViews(packageName, R.layout.notification_navigation).apply {
            setTextViewText(R.id.widget_label, state.label)
            setTextViewText(R.id.widget_primary, state.primary)
            setTextViewText(R.id.widget_next, state.next)
            setTextViewText(R.id.widget_progress_text, progressText)
            setImageViewResource(R.id.widget_arrow_icon, arrowRes)
            applyProgressSegments(this, progressClamped)
        }
        val collapsedView = RemoteViews(packageName, R.layout.notification_navigation_collapsed).apply {
            setTextViewText(R.id.widget_primary, state.primary)
            setImageViewResource(R.id.widget_arrow_icon, arrowRes)
        }

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_arrow_right)
            .setStyle(NotificationCompat.DecoratedCustomViewStyle())
            .setCustomContentView(collapsedView)
            .setCustomBigContentView(expandedView)
            .setCustomHeadsUpContentView(expandedView)
            .setOngoing(true)
            .setAutoCancel(false)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setCategory(NotificationCompat.CATEGORY_NAVIGATION)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .build()
    }

    private fun applyProgressSegments(views: RemoteViews, progress: Int) {
        val filled = (progress * PROGRESS_SEGMENT_IDS.size + 50) / 100
        PROGRESS_SEGMENT_IDS.forEachIndexed { index, viewId ->
            val drawable = if (index < filled) R.drawable.bg_progress_filled else R.drawable.bg_progress_empty
            views.setInt(viewId, "setBackgroundResource", drawable)
        }
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
        // Recreate so updated bypassDnd / importance settings apply.
        manager.deleteNotificationChannel(CHANNEL_ID)
        // IMPORTANCE_LOW: status bar에는 표시되지만 heads-up 팝업은 뜨지 않음.
        // 잠금화면/알림 패널 표시 + Foreground Service 유지에는 영향 없음.
        val channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_LOW,
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

        private val PROGRESS_SEGMENT_IDS = intArrayOf(
            R.id.widget_progress_seg_0,
            R.id.widget_progress_seg_1,
            R.id.widget_progress_seg_2,
            R.id.widget_progress_seg_3,
            R.id.widget_progress_seg_4,
            R.id.widget_progress_seg_5,
            R.id.widget_progress_seg_6,
            R.id.widget_progress_seg_7,
            R.id.widget_progress_seg_8,
            R.id.widget_progress_seg_9,
            R.id.widget_progress_seg_10,
        )
    }
}
