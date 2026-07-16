package routing

import "testing"

// This is testing if it returns the same hash value for the same device in the same bucket
func Test_isDeterministic(t *testing.T) {
	first := BucketFor("sensor-a1b2c3", "enable_ai_processor")
	second := BucketFor("sensor-a1b2c3", "enable_ai_processor")

	if first != second {
		t.Errorf("expected to get the same hashvalue, but received different hash values")
	}

}

// This is testing to see if the same device can fall into a different bucket feature instead of the same one
func Test_isSameFeature(t *testing.T) {
	first_bucket := BucketFor("sensor-a1b2c3", "enable_ai_processor")
	second_bucket := BucketFor("sensor-a1b2c3", "todolist")
	if first_bucket == second_bucket {
		t.Errorf("expected a different hash value for a different bucket feature, but got the same")
	}
}

// This is testing to see if the bucket values retrieved from the function are between 1 and 100.
func Test_isOneToHundred(t *testing.T) {
	devices := []string{"sensor-a1b2c3", "sensor-a1b6c7", "sensor-a1b9c3", "sensor-a1b10c3"}

	for _, deviceID := range devices {
		bucket := BucketFor(deviceID, "enable_ai_processor")
		if bucket < 1 || bucket > 100 {
			t.Errorf("expected the bucket value to be between 1 and 100. Failed")
		}
	}
}
