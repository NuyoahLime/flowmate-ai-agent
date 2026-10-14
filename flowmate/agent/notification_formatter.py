from flowmate.schemas import DynamicSideEffectProposal, DynamicPlanningState


class NotificationGroundingError(Exception):
    pass


class NotificationFormatter:
    def build_proposal(self, state: DynamicPlanningState) -> DynamicSideEffectProposal:
        if state.selected_event is None:
            raise NotificationGroundingError("Notification requires a selected event.")

        event = state.selected_event
        required_event_fields = ("title", "start_time", "location")
        missing_fields = [field for field in required_event_fields if not event.get(field)]
        if missing_fields:
            raise NotificationGroundingError(
                f"Selected event missing fields for notification: {', '.join(missing_fields)}"
            )

        message_parts = [
            (
                f"Your {event['start_time']} meeting '{event['title']}' "
                f"is at {event['location']}."
            )
        ]

        weather_result = state.final_result.weather_result if state.final_result else None
        if weather_result:
            message_parts.append(
                "Weather: "
                f"{weather_result['condition']}, "
                f"{weather_result['temperature_c']}C."
            )

        navigation_result = (
            state.final_result.navigation_result if state.final_result else None
        )
        if navigation_result:
            message_parts.append(
                "Route: "
                f"{navigation_result['duration_minutes']} minutes, "
                f"traffic {navigation_result['traffic']}."
            )

        return DynamicSideEffectProposal(
            tool_name="notification_tool",
            arguments={
                "title": "Morning commute ready",
                "message": " ".join(message_parts),
                "channel": "mobile",
            },
            reason="User requested notification after dynamic result is ready.",
        )
