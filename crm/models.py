from django.db import models


class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    company = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company", "last_name", "first_name")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return self.full_name


class Deal(models.Model):
    class Stage(models.TextChoices):
        LEAD = "lead", "Lead"
        INITIAL_OUTREACH = "initial_outreach", "Initial outreach"
        FREE_TRIAL = "free_trial", "Free trial"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        NO_TRACTION = "no_traction", "No traction"

    STAGE_STYLES = {
        Stage.LEAD: "slate",
        Stage.INITIAL_OUTREACH: "blue",
        Stage.FREE_TRIAL: "purple",
        Stage.WON: "green",
        Stage.LOST: "red",
        Stage.NO_TRACTION: "amber",
    }

    name = models.CharField(max_length=150)
    company = models.CharField(max_length=150)
    stage = models.CharField(
        max_length=30,
        choices=Stage.choices,
        default=Stage.LEAD,
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    expected_close_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True)
    contacts = models.ManyToManyField(Contact, related_name="deals", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("stage", "-updated_at")

    def __str__(self) -> str:
        return f"{self.name} ({self.company})"

    @property
    def stage_style(self) -> str:
        return self.STAGE_STYLES[self.stage]

    def save(self, *args, **kwargs):
        previous_stage = None
        is_new = self.pk is None

        if not is_new:
            previous_stage = (
                type(self).objects.filter(pk=self.pk).values_list("stage", flat=True).first()
            )

        super().save(*args, **kwargs)

        if is_new:
            DealActivity.objects.create(
                deal=self,
                entry_type=DealActivity.EntryType.STAGE_CHANGE,
                content=f"Deal created in {self.get_stage_display()}.",
            )
        elif previous_stage and previous_stage != self.stage:
            previous_label = self.Stage(previous_stage).label
            DealActivity.objects.create(
                deal=self,
                entry_type=DealActivity.EntryType.STAGE_CHANGE,
                content=(
                    f"Stage changed from {previous_label} to {self.get_stage_display()}."
                ),
            )


class DealActivity(models.Model):
    class EntryType(models.TextChoices):
        NOTE = "note", "Note"
        STAGE_CHANGE = "stage_change", "Stage change"

    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name_plural = "Deal activities"

    def __str__(self) -> str:
        return f"{self.get_entry_type_display()} for {self.deal}"
