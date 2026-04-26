use std::collections::VecDeque;
use std::time::{Duration, Instant};

#[allow(dead_code)]
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChildState {
    Stopped,
    Running,
    Degraded(String),
}

#[derive(Debug)]
#[allow(dead_code)]
pub struct RestartLimiter {
    max_restarts: usize,
    window: Duration,
    attempts: VecDeque<Instant>,
}

#[allow(dead_code)]
impl RestartLimiter {
    pub fn new(max_restarts: usize, window: Duration) -> Self {
        Self {
            max_restarts,
            window,
            attempts: VecDeque::new(),
        }
    }

    pub fn record_and_check(&mut self, now: Instant) -> bool {
        while let Some(front) = self.attempts.front().copied() {
            if now.duration_since(front) > self.window {
                self.attempts.pop_front();
            } else {
                break;
            }
        }
        if self.attempts.len() >= self.max_restarts {
            return false;
        }
        self.attempts.push_back(now);
        true
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SupervisorStatus {
    pub state: String,
    pub agent_state: String,
    pub control_bridge_state: String,
    pub last_error: Option<String>,
}

impl SupervisorStatus {
    #[allow(dead_code)]
    pub fn running() -> Self {
        Self {
            state: "running".into(),
            agent_state: "running".into(),
            control_bridge_state: "running".into(),
            last_error: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restart_limiter_allows_five_restarts_in_window_then_blocks() {
        let mut limiter = RestartLimiter::new(5, Duration::from_secs(600));
        let now = Instant::now();
        for offset in 0..5 {
            assert!(limiter.record_and_check(now + Duration::from_secs(offset)));
        }
        assert!(!limiter.record_and_check(now + Duration::from_secs(6)));
    }

    #[test]
    fn restart_limiter_recovers_after_window() {
        let mut limiter = RestartLimiter::new(1, Duration::from_secs(10));
        let now = Instant::now();
        assert!(limiter.record_and_check(now));
        assert!(!limiter.record_and_check(now + Duration::from_secs(1)));
        assert!(limiter.record_and_check(now + Duration::from_secs(11)));
    }
}
